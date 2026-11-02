(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const publicReplay = document.querySelector('meta[name="factory-demo-mode"]')?.content === 'public-replay';
  const publicAssets = {'/api/status':'./data/status.json','/api/recorded-episode':'./data/episode.json','/api/recorded-note':'./data/note.json','/api/evaluation':'./data/evaluation.json'};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = {preserve:'Preserve',reschedule:'Reorder',reroute:'Reroute',always_replan:'Always replan',fixed_interval:'Fixed interval',solver_selection:'Solver selection',meta:'Meta supervisor'};
  const colors = ['#30755a','#597a8b','#997447','#708953','#7c6c91','#398687','#a16f76','#94915c'];
  let episode = null, frameIndex = 0, preview = null, running = false, metaReady = false;
  let sourceId = 'recorded', noteResult = null, noteId = null, noteContextKey = null;
  const status = (text,error=false) => { $('console-status').textContent=text; $('console-status').classList.toggle('error',error); };
  const fmt = value => Number.isFinite(value) ? Number(value.toFixed(2)).toLocaleString() : '—';
  async function request(path, options) { if(publicReplay&&options?.method&&options.method!=='GET')throw Error('Public replay is read-only. Run locally for fresh simulation and inference.'); const target=publicReplay?publicAssets[path]:path; if(!target)throw Error('This action is available in the local application.'); const response=await fetch(target,options);const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');return data; }
  function busy(value) {running=value;document.body.classList.toggle('running',value);$('start-episode').disabled=value||publicReplay;$('episode-policy').disabled=value||publicReplay;$('recorded').disabled=value; $('replay-note').disabled=value; updateNoteButtons();}
  async function connection() {try {const data=await request('/api/status');metaReady=!publicReplay&&data.providers.meta.configured; updateNoteButtons();$('credit-status').textContent=publicReplay?'PUBLIC REPLAY · recorded real Meta runs. No key, account access, or inference charges. Run locally for new executions.':`Meta key ${metaReady?'configured':'not configured'} · local $1 guard${data.budget?` · $${data.budget.reserved_or_estimated_usd.toFixed(3)} recorded/reserved`:''}. Not the account balance.`;}catch(error){$('credit-status').textContent=error.message;}}
  async function recorded() {try {const data=await request('/api/recorded-episode');episode=data.episode;sourceId='recorded';frameIndex=Math.max(0,episode.frames.findIndex(f=>f.time===25));preview=null;render('RECORDED META EXECUTION');status('Loaded a recorded real Meta run. Replaying it spends no API credits.');}catch(error){status(error.message,true);}}
  async function execute() {
    if(running)return;const policy=$('episode-policy').value;
    if(policy==='meta'&&!metaReady){status('Add your Meta key locally before starting a live model episode.',true);return;}
    busy(true);status(policy==='meta'?'Starting real Meta-supervised execution. Local credit guard is active.':'Executing the conventional simulation. No API credits used.');
    try {
      const job=await request('/api/episode',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({policy,provider:'meta'})});
      await followJob(job);
    }catch(error){status(error.message,true);}finally{busy(false);connection();}
  }
  async function followJob(job) {
      while(true){
        const state=await request(`/api/jobs/${job.job_id}`);
        if(state.status==='running'&&state.frames.length&&(!episode||episode.run_id!==job.job_id||episode.frames.length!==state.frames.length)){
          sourceId=job.job_id;episode={run_id:job.job_id,scenario:state.scenario,policy:state.policy,frames:state.frames,realized_metrics:null,failures:[],limitations:['Live execution in progress; final results are not available yet.']};
          frameIndex=episode.frames.length-1;preview=null;render('LIVE EXECUTION · IN PROGRESS');
        }
        if(state.progress.length){const latest=state.progress.at(-1);status(`${latest.time!==undefined?`Minute ${latest.time} · `:''}${latest.stage.replaceAll('_',' ')}${latest.tool?` · ${latest.tool}`:''}${latest.request?` ${latest.request}`:''}`);}
        if(state.status==='completed'){episode=state.result;sourceId=job.job_id;frameIndex=episode.frames.length-1;preview=null;render('NEW EXECUTION · COMPLETED');status(`${episode.status.replaceAll('_',' ')} · ${episode.realized_metrics?.model_calls||0} model requests · ${episode.failures.length} failures/fallbacks.`);break;}
        if(state.status==='failed')throw Error(state.error);
        await new Promise(resolve=>setTimeout(resolve,500));
      }
  }
  function render(mode) {
    const f=episode.frames[frameIndex]; updateNoteButtons(); $('note-context').textContent=`Grounded at minute ${f.time} · source ${sourceId} · current outages: ${Object.entries(f.state.available_at).map(([m,t])=>`${m} expected at ${t}`).join(', ')||'none'}.`; $('frame-slider').max=episode.frames.length-1;$('frame-slider').value=frameIndex;$('frame-slider').disabled=false;$('frame-time').textContent=f.time;$('execution-mode').textContent=mode||$('execution-mode').textContent;$('export-episode').disabled=false;
    const counts={active:0,paused:0,queued:0,completed:0,blocked:0};for(const op of f.factory.operations)if(op.status in counts)counts[op.status]++;
    $('state-counts').innerHTML=Object.entries(counts).map(([k,v])=>`<span><b>${v}</b>${k}</span>`).join('');
    $('event-buttons').innerHTML=episode.frames.map((frame,i)=>frame.events.length||i===0||i===episode.frames.length-1?`<button class="event-button" data-frame="${i}" aria-pressed="${i===frameIndex}">${frame.time}m · ${i===0?(frame.time===0?'Shift start':'Branch start'):frame.events.length?esc(frame.events.map(e=>e.kind.replaceAll('_',' ')).join(' + ')):'Completed execution'}</button>`:'').join('');
    for(const button of document.querySelectorAll('[data-frame]'))button.onclick=()=>{frameIndex=Number(button.dataset.frame);preview=null;render();};
    $('factory-machines').innerHTML=f.factory.machines.map(m=>`<div class="machine ${m.status==='down'?'down':''}"><div class="machine-name">${esc(m.machine)}<i></i></div><div class="machine-status">${esc(m.status)}</div><p>${m.current_operation?esc(m.current_operation):'No active operation'}</p><p>${m.status==='down'?`Forecast available: minute ${m.forecast_available_at}`:'Available to the dispatcher'}</p><p class="queue">QUEUE · ${m.queue.length?esc(m.queue.join(' → ')):'empty'}</p></div>`).join('');
    $('operation-register').innerHTML=f.factory.operations.map(o=>`<tr><td>${esc(o.operation)}</td><td>${esc(o.machine)}</td><td><span class="state-tag ${o.status}">${esc(o.status)}</span></td><td>${o.worked_minutes} min</td><td>${o.remaining_minutes} min</td></tr>`).join('');
    const decision=f.decision;
    const last=episode.frames.slice(0,frameIndex+1).findLast(frame=>frame.decision);
    const d=decision||last?.decision;
    $('current-event').textContent=f.events.length?f.events.map(e=>`${e.kind.replaceAll('_',' ')} · ${e.machine}\n${e.source}`).join('\n\n'):'Clock/state observation. No new operational incident at this boundary.';
    $('experiment-budget').textContent=`${decision?.candidates?.length||0} / 3 EXPERIMENTS`;
    $('request-budget').textContent=d?`${d.model_requests} model requests at minute ${d.time}`:'No model request';
    $('hypotheses').innerHTML=(decision?.tool_trace||[]).filter(t=>t.request?.hypothesis).map(t=>`<div class="hypothesis"><b>${esc(t.origin==='mandatory_baseline'?'Mandatory baseline':names[t.request.policy]||t.request.policy)}</b> · ${esc(t.request.hypothesis)}</div>`).join('');
    $('episode-candidates').innerHTML=(decision?.candidates||[]).map((c,i)=>`<button class="candidate ${(preview===i||(preview===null&&c.policy===decision.selected_policy))?'active':''}" data-candidate="${i}"><div class="name">${esc(names[c.policy])}${c.policy===decision.selected_policy?' · selected':''}</div><div class="value">${c.nominal_metrics.weighted_tardiness_minutes}<small> min</small></div><p>forecast weighted delay</p><p class="tradeoffs">${c.nominal_metrics.on_time_orders}/${c.nominal_metrics.total_orders} on time · ${c.nominal_metrics.rerouted_operations} reroutes</p><p>Worst tested: ${c.worst_tested_weighted_tardiness} min</p></button>`).join('')||'<p class="caption">No candidate experiment requested at this boundary.</p>';
    for(const button of document.querySelectorAll('[data-candidate]'))button.onclick=()=>{preview=Number(button.dataset.candidate);render();};
    $('tool-trace').innerHTML=d?(d.tool_trace?.length?d.tool_trace.map((t,i)=>`<div class="tool"><span class="index">${String(i+1).padStart(2,'0')}</span><span>${esc(t.tool)}${t.request?.policy?` / ${esc(t.request.policy)}`:''}${t.origin?' / mandatory':''}</span><span class="tool-outcome">${t.result?.error?'rejected':t.result?.cache_hit?'cached':'completed'}</span></div>`).join(''):'<p class="caption">Conventional solver/simulation execution; no model tool trace.</p>'):'<p class="caption">No decision yet.</p>';
    $('decision-badge').textContent=d?.action||'—';$('decision-badge').classList.toggle('fallback',d?.action==='FALLBACK');$('decision-time').textContent=d?`Decision at minute ${d.time}${!decision?' · most recent prior decision':''}`:'Shift begins with a validated schedule.';const measured=d?.predicted_metrics; $('decision-evidence').textContent=d?.verified_evidence?.summary||(measured?`${d.action}: forecast weighted delay ${measured.weighted_tardiness_minutes} min; ${measured.on_time_orders}/${measured.total_orders} orders on time; ${measured.rerouted_operations} reroutes; ${measured.queued_start_shift_minutes} min queued start shifts. Forecasts, not realized outcomes.`:d?.failure?.error||'No intervention requested.'); $('model-rationale').textContent=d?.evidence_summary||'No model rationale at this observation.';$('constraint-result').textContent=d?.action==='FALLBACK'?'Validated guard applied; agent failure recorded.':'✓ Enacted schedule passed the independent constraint checker.';$('decision-cost').textContent=d?.model_requests?`Estimated token cost for this decision: ${Number.isFinite(d.estimated_cost_usd)?'$'+d.estimated_cost_usd.toFixed(4):'unverified'}. Provider billing is authoritative.`:'No API charge for this observation.';
    const shown=preview===null?f.plan:decision.candidates[preview].plan;$('episode-gantt').innerHTML=gantt(shown,f);$('gantt-caption').textContent=`${preview===null?'Enacted plan':'Candidate forecast preview · not applied'}. Executed work through minute ${f.time} is solid; remaining work is a forecast from this observation. Scroll horizontally on smaller screens.`;
    const m=episode.realized_metrics;
    $('realized-metrics').innerHTML=m?[[m.weighted_tardiness_minutes,'priority-weighted delay / min'],[`${m.on_time_orders}/${m.total_orders}`,'orders on time'],[m.revision_count,'optional plan revisions'],[m.rerouted_operations,'reroute transitions'],[m.model_calls,'model requests'],[Number.isFinite(m.estimated_model_cost_usd)?'$'+m.estimated_model_cost_usd.toFixed(3):'unknown','estimated model cost']].map(([v,label])=>`<div class="metric"><strong>${esc(v)}</strong><span>${esc(label)}</span></div>`).join(''):'<p class="muted">Episode did not finish; outcomes are unavailable.</p>';
    $('episode-limitations').textContent=`Final metrics are from the complete recorded/executed shift, even when inspecting an earlier observation. Policy: ${names[episode.policy]}. ${episode.limitations.join(' ')}${episode.branch?' This is a new maintenance-note branch. Past observations are preserved; revision and model-use counters cover the branch only.':''}`;$('episode-failures').innerHTML=episode.failures.map(failure=>`<div class="failure">Minute ${failure.time??'—'} · ${esc(failure.error)} · ${esc(failure.fallback||'no fallback')}</div>`).join('');
  }
  function gantt(plan, frame) {
    const maximum=Math.ceil(Math.max(...plan.assignments.map(a=>a.end),frame.time)/50)*50||50,x=t=>110+t/maximum*840;
    const segments={};
    for(let i=1;i<=frameIndex;i++)for(const [op,record] of Object.entries(episode.frames[i].state.progress)){
      const previous=episode.frames[i-1].state.progress[op];const delta=record.worked-(previous?.worked||0);
      if(delta>0){const end=record.completed_at??episode.frames[i].time;(segments[op]??=[]).push([end-delta,end]);}
    }
    const history=[];const open={};
    for(const f of episode.frames.slice(0,frameIndex+1))for(const event of f.events){if(event.kind==='outage')open[event.machine]=event.time;if(event.kind==='repaired'&&open[event.machine]!==undefined){history.push([event.machine,open[event.machine],event.time]);delete open[event.machine];}}
    for(const [machine,start] of Object.entries(open))history.push([machine,start,frame.time]);
    let svg='<svg viewBox="0 0 980 245" role="img" aria-label="Executed and forecast production operations by machine">';
    for(let time=0;time<=maximum;time+=50)svg+=`<line x1="${x(time)}" y1="25" x2="${x(time)}" y2="215" stroke="#e3e9df"/><text x="${x(time)}" y="235" fill="#718275" font-size="9" text-anchor="middle">${time}</text>`;
    episode.scenario.machines.forEach((machine,index)=>{
      const y=30+index*46;svg+=`<text x="0" y="${y+19}" fill="#405b4b" font-size="11" font-weight="600">${esc(machine)}</text><rect x="110" y="${y}" width="840" height="31" rx="2" fill="#f4f7f0"/>`;
      for(const [m,start,end] of history)if(m===machine)svg+=`<rect x="${x(start)}" y="${y}" width="${Math.max(0,x(end)-x(start))}" height="31" fill="#efd9b9"/>`;
      if(frame.state.available_at[machine]>frame.time)svg+=`<rect x="${x(frame.time)}" y="${y}" width="${x(frame.state.available_at[machine])-x(frame.time)}" height="31" fill="#efd9b9" opacity=".45"/>`;
      for(const a of plan.assignments.filter(a=>a.machine===machine)){
        const order=episode.scenario.orders.findIndex(o=>o.operations.some(op=>op.id===a.operation)),color=colors[order%colors.length];
        const spans=(segments[a.operation]||[]).map(s=>[...s,false]);const progress=frame.state.progress[a.operation];
        if(!progress||progress.completed_at===null){const start=progress?Math.max(frame.time,frame.state.available_at[machine]||0):a.start;if(a.end>start)spans.push([start,a.end,true]);}
        for(const [start,end,forecast] of spans){const width=x(end)-x(start);svg+=`<g><title>${esc(a.operation)} · ${start}–${end} min · ${forecast?'forecast':'executed'}</title><rect x="${x(start)+.5}" y="${y+4}" width="${Math.max(.5,width-1)}" height="23" rx="2" fill="${color}" opacity="${forecast ? 0.4 : 1}"/>${width>29?`<text x="${x(start)+width/2}" y="${y+19}" font-size="8" text-anchor="middle" fill="${forecast?'#203f30':'white'}">${esc(a.operation.split('/')[0].replace('ORD-','#'))}</text>`:''}</g>`;}
      }
    });
    return svg+`<line x1="${x(frame.time)}" y1="15" x2="${x(frame.time)}" y2="215" stroke="#315b41" stroke-dasharray="4 3"/><text x="${x(frame.time)}" y="11" text-anchor="middle" font-size="9" fill="#315b41">OBSERVED ${frame.time}m</text></svg>`;
  }
  async function evaluation() {
    try{const s=await request('/api/evaluation');$('evaluation-description').textContent=`Version ${s.configuration.version} · ${s.configuration.seeds.length} frozen scenarios · revision ${s.source_revision.slice(0,7)} · ${s.rows.filter(r=>r.policy==='meta').length} predeclared Meta attempts. Means below include fallback outcomes, with failures labelled.`;
      $('aggregate-results').innerHTML=Object.entries(s.aggregate).filter(([p])=>p!=='meta').map(([p,r])=>`<tr><td>${names[p]}</td><td>${r.attempted}</td><td>${r.failed_or_fallback}</td><td>${fmt(r.metrics.weighted_tardiness_minutes?.mean)} ± ${fmt(r.metrics.weighted_tardiness_minutes?.std)}</td><td>${fmt(r.metrics.revision_count?.mean)}</td><td>${fmt(r.metrics.model_calls?.mean)}</td></tr>`).join('');
      const paired=s.meta_paired_rows, policies=[...new Set(paired.map(r=>r.policy))];const mean=(rows,key)=>rows.reduce((sum,r)=>sum+(r.metrics?.[key]||0),0)/rows.length;
      $('paired-results').innerHTML=policies.map(p=>{const rows=paired.filter(r=>r.policy===p),valid=rows.filter(r=>r.metrics);return `<tr><td>${names[p]}</td><td>${rows.length}</td><td>${rows.filter(r=>r.status!=='completed').length}</td><td>${valid.length?fmt(mean(valid,'weighted_tardiness_minutes')):'—'}</td><td>${valid.length?fmt(mean(valid,'on_time_orders')):'—'}</td></tr>`;}).join('')||'<tr><td colspan="5">No Meta evaluation has been attempted.</td></tr>';
      $('scenario-results').innerHTML=s.rows.map(r=>`<tr><td>${r.seed}</td><td>${names[r.policy]}</td><td>${esc(r.status.replaceAll('_',' '))}</td><td>${fmt(r.metrics?.weighted_tardiness_minutes)}</td><td>${fmt(r.metrics?.model_calls)}</td></tr>`).join('');$('evaluation-failures').innerHTML=s.rows.flatMap(r=>r.failures.map(f=>`<div class="failure">Seed ${r.seed} / ${names[r.policy]} / minute ${f.time??'—'} · ${esc(f.error)}</div>`)).join('');
    }catch(error){$('evaluation-description').textContent=error.message;}
  }
  function currentNoteKey() { return `${sourceId}:${frameIndex}:${$('maintenance-note').value.trim()}`; }
  function updateNoteButtons() {
    const valid=Boolean(noteId&&noteResult?.interpretation.status==='validated'&&noteResult.interpretation.events.length&&noteContextKey===currentNoteKey());
    $('interpret-note').disabled=running||publicReplay||!metaReady||!episode; $('start-episode').disabled=running||publicReplay; $('episode-policy').disabled=running||publicReplay;
    $('apply-note').disabled=running||publicReplay||!valid;
    $('apply-note-meta').disabled=running||publicReplay||!valid||!metaReady;
  }
  function showNote(result, recorded=false) {
    const value=result.interpretation;
    $('note-result').className=`note-result ${value.status}`;
    const headline=value.status==='validated'?'Claims independently validated.':value.status==='clarification_required'?'Clarification required — no update applied.':'Rejected — no update applied.';
    $('note-result').innerHTML=`<strong>${headline}</strong>${recorded?'<p class="caption">Recorded real Meta extraction and completed branch. No new inference.</p>':'<p class="caption">The source recording is unchanged. Apply explicitly to create a new simulation branch.</p>'}${value.events.map(e=>`<div class="note-event"><b>${esc(e.machine)} · ${esc(e.kind.replaceAll('_',' '))}</b><br>${e.estimated_repair_at!==null?`New forecast availability: minute ${e.estimated_repair_at}`:'Confirmed repair observed now'} · observed at minute ${e.time}<br><span class="note-quote">“${esc(e.source)}”</span></div>`).join('')}${value.notices.map(n=>`<div class="note-event">${esc(n.machine)} · unchanged availability · no state change<br><span class="note-quote">“${esc(n.evidence)}”</span></div>`).join('')}${value.questions.map(q=>`<div class="note-event">Clarify: ${esc(q)}</div>`).join('')}${value.errors.map(e=>`<div class="note-event">${esc(e)}</div>`).join('')}<details><summary>Extracted claims and quoted evidence</summary><pre class="note-quote">${esc(JSON.stringify(value.proposed_claims,null,2))}</pre></details><p class="caption">${result.cache_hit?'Cached extraction reused; no new API charge.':recorded?'Recorded interpretation cost: ':'New interpretation token-cost estimate: '}${!result.cache_hit&&Number.isFinite(value.estimated_cost_usd)?'$'+value.estimated_cost_usd.toFixed(4):''} ${esc(value.validation_note)}</p>`;
    updateNoteButtons();
  }
  async function interpretOperatorNote() {
    if(running||!episode)return;
    const text=$('maintenance-note').value.trim();if(!text){status('Enter a maintenance note first.',true);return;}
    const context=currentNoteKey();busy(true);status('Meta is extracting claims. Independent grounding and state checks follow; no update is applied yet.');
    try{
      const result=await request('/api/interpret-note',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({note:text,source_id:sourceId,frame_index:frameIndex,provider:'meta'})});
      noteResult=result;noteId=result.interpretation_id;noteContextKey=context;showNote(result);
      status(`${result.interpretation.status.replaceAll('_',' ')} · ${result.interpretation.events.length} state-changing events · ${result.cache_hit?'cached, no new inference':'one Meta interpretation request'}.`);
    }catch(error){status(error.message,true);}finally{busy(false);connection();}
  }
  async function applyNote(policy) {
    if(running||!noteId||noteContextKey!==currentNoteKey())return;
    busy(true);status('Revalidating the note against its exact source observation and creating a new recovery branch…');
    try{const job=await request('/api/note-branch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({interpretation_id:noteId,policy,provider:'meta'})});await followJob(job);noteId=null;status('Validated note applied in a new branch. The source recording and completed work are unchanged.');}
    catch(error){status(error.message,true);}finally{busy(false);connection();}
  }
  async function replayNote() {
    if(running)return;
    try{const data=await request('/api/recorded-note');episode=data.branch;sourceId='recorded-note';frameIndex=Math.max(0,episode.frames.findIndex(f=>f.time===data.interpretation.observed_at&&f.events.length));preview=null;noteId=null;noteResult={interpretation:data.interpretation};$('maintenance-note').value=data.interpretation.note;render('RECORDED NOTE BRANCH');showNote(noteResult,true);status('Loaded the recorded real note-to-recovery workflow. No new inference or simulation was run.');}
    catch(error){status(error.message,true);}
  }
  $('interpret-note').onclick=interpretOperatorNote;$('apply-note').onclick=()=>applyNote('solver_selection');$('apply-note-meta').onclick=()=>applyNote('meta');$('replay-note').onclick=replayNote;
  $('maintenance-note').oninput=()=>{noteId=null;noteResult=null;updateNoteButtons();$('note-result').className='note-result';$('note-result').textContent='Note changed. Interpret and validate before applying any update.';};
  for(const button of document.querySelectorAll('[data-note-example]'))button.onclick=()=>{$('maintenance-note').value=button.dataset.noteExample;$('maintenance-note').dispatchEvent(new Event('input'));};
  $('frame-slider').oninput=()=>{frameIndex=Number($('frame-slider').value);preview=null;render();};$('start-episode').onclick=execute;$('recorded').onclick=recorded;$('refresh-evaluation').onclick=evaluation;
  $('export-episode').onclick=()=>{if(!episode)return;const url=URL.createObjectURL(new Blob([JSON.stringify(episode,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='factory-sequential-episode.json';a.click();URL.revokeObjectURL(url);};
  connection();recorded();evaluation();
})();
