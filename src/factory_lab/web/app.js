'use strict';
const $ = id => document.getElementById(id);
const labels = {preserve:'Preserve commitments',reschedule:'Reorder queued work',reroute:'Allow eligible reroutes'};
const descriptions = {preserve:'Keep queue order and machine assignments.',reschedule:'Change order; keep existing machine routes.',reroute:'Change order and use compatible machines.'};
const colors = ['#257358','#5a7789','#8b6e52','#698251','#76698b','#3c8586','#9a6b72','#8d8c5e'];
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let report = null, selected = 'preserve', busy = false, providers = {};

function notice(message, error=false) { $('notice').textContent=message; $('notice').classList.toggle('error',error); }
function settings() { return {machine:$('machine').value,outage_at:Number($('outage').value),repair_at:Number($('repair').value),provider:$('provider').value}; }
function setBusy(value) { busy=value; document.body.classList.toggle('busy',value); $('run').disabled=value; $('refresh').disabled=value; for(const id of ['machine','outage','repair','provider']) $(id).disabled=value; updateProvider(); }
function updateProvider() { const state=providers[$('provider').value]; $('agent').disabled=busy||!state?.configured; $('provider-status').classList.toggle('ready',Boolean(state?.configured)); $('provider-status').textContent=state?.configured ? `Key configured · ${state.model}. Live access not yet verified.` : 'Add the provider key to the local .env file, then refresh.'; }
async function refresh() { try { const response=await fetch('/api/status'); if(!response.ok) throw Error('Unable to check local configuration'); providers=(await response.json()).providers; updateProvider(); } catch(error) { notice(error.message,true); } }
async function run(agent=false) {
  if(busy) return;
  const config=settings();
  if(!Number.isInteger(config.outage_at)||!Number.isInteger(config.repair_at)||config.repair_at<=config.outage_at) { notice('Enter whole minutes, with expected return later than the outage.',true); return; }
  setBusy(true); notice(agent?'Meta supervisor is testing recovery options. This may take a few minutes…':'Solving and replaying three recovery options…');
  try {
    const response=await fetch(agent?'/api/agent':'/api/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
    const data=await response.json(); if(!response.ok) throw Error(data.error||'The experiment failed.');
    report=data;
    if(data.agent) { for(const candidate of data.agent.experiments) { const i=report.candidates.findIndex(c=>c.policy===candidate.policy); if(i>=0) report.candidates[i]=candidate; } selected=data.agent.selected_policy; }
    else selected='preserve';
    render();
    notice(agent?`Live model run complete · ${data.agent.model_requests} requests · ${data.agent.experiments.length} experiments · plan independently validated.`:`Simulation complete · ${data.candidates.length} recovery options validated · no AI used.`);
  } catch(error) { notice(error.message,true); }
  finally { setBusy(false); }
}
function render() {
  const state=report.observation, incident=report.incident;
  $('observation-time').textContent=`Minute ${state.now}`;
  $('machines').innerHTML=report.scenario.machines.map(machine=>{
    const offline=machine===incident.machine && incident.estimated_repair_at>state.now;
    const active=Object.entries(state.progress).find(([,p])=>p.machine===machine&&p.completed_at===null);
    const status=offline?'Offline':active?'Running':'Available';
    const detail=offline?`Expected return · min ${incident.estimated_repair_at}`:active?`${active[0].split('/')[0]} · ${active[1].worked} min worked`:'Ready for the next operation';
    return `<div class="machine-card ${offline?'offline':''}"><div class="machine-top">${escapeHtml(machine)}<span class="machine-light"></span></div><div class="machine-state">${status}</div><div class="machine-job">${escapeHtml(detail)}</div></div>`;
  }).join('');
  $('run-id').textContent=`Run ${report.run_id||'local'}`;
  $('download').disabled=false;
  renderSelection(); renderAgent();
}
function renderSelection() {
  const candidate=report.candidates.find(c=>c.policy===selected);
  $('candidates').innerHTML=report.candidates.map(c=>{
    const m=c.nominal_metrics;
    return `<button class="candidate" data-policy="${c.policy}" aria-pressed="${c.policy===selected}">${c.policy===selected?'<span class="selected-dot"></span>':''}<div class="candidate-name">${labels[c.policy]}</div><div class="candidate-description">${descriptions[c.policy]}</div><div class="candidate-number">${m.weighted_tardiness_minutes}<small> min</small></div><div class="candidate-label">priority-weighted delay</div><div class="candidate-foot"><span>${m.on_time_orders}/${m.total_orders} orders on time</span><span>${m.rerouted_operations} rerouted</span></div></button>`;
  }).join('');
  for(const button of document.querySelectorAll('[data-policy]')) button.addEventListener('click',()=>{selected=button.dataset.policy;renderSelection();});
  $('schedule-title').textContent=labels[selected];
  $('timeline').innerHTML=timeline(candidate.plan,false);
  $('original-timeline').innerHTML=timeline(report.original_plan,true);
  $('orders').innerHTML=candidate.nominal_metrics.orders.map(o=>`<tr><td>${escapeHtml(o.order)}</td><td>${o.priority}</td><td>${o.due} min</td><td>${o.completed_at} min</td><td class="${o.tardiness_minutes?'late':'on-time'}">${o.tardiness_minutes?`+${o.tardiness_minutes} min`:'On time'}</td></tr>`).join('');
  $('validation').textContent=candidate.constraint_errors.length?`${candidate.constraint_errors.length} constraint failures`:`✓ Selected plan passed all checks · solver ${candidate.plan.solver_status.toLowerCase()}`;
}
function timeline(plan,original) {
  const machines=report.scenario.machines, incident=report.incident, state=report.observation;
  const maximum=Math.ceil(Math.max(...report.candidates.flatMap(c=>c.plan.assignments.map(a=>a.end)),...report.original_plan.assignments.map(a=>a.end))/50)*50;
  const x=t=>110+(t/maximum)*840;
  let svg=`<svg viewBox="0 0 980 252" role="img" aria-label="${original?'Original healthy':'Recovery'} production schedule by machine. Hover over operations for times."><rect width="980" height="252" fill="white"/>`;
  for(let t=0;t<=maximum;t+=50) svg+=`<line x1="${x(t)}" y1="22" x2="${x(t)}" y2="218" stroke="#e8ede7"/><text x="${x(t)}" y="239" text-anchor="middle" fill="#75847d" font-size="10">${t}</text>`;
  machines.forEach((machine,i)=>{
    const y=30+i*46;
    svg+=`<text x="0" y="${y+18}" fill="#4d635a" font-size="11" font-weight="600">${escapeHtml(machine)}</text><rect x="110" y="${y}" width="840" height="30" rx="3" fill="#f5f7f2"/>`;
    if(!original&&machine===incident.machine) svg+=`<rect x="${x(state.now)}" y="${y-3}" width="${x(incident.estimated_repair_at)-x(state.now)}" height="36" rx="3" fill="#f5dfc1"/><text x="${x(state.now)+4}" y="${y-7}" fill="#ac6a31" font-size="8">DOWNTIME</text>`;
    for(const entry of plan.assignments.filter(a=>a.machine===machine)) {
      const orderIndex=report.scenario.orders.findIndex(o=>o.operations.some(op=>op.id===entry.operation));
      const color=colors[orderIndex%colors.length], record=state.progress[entry.operation];
      let spans=[[entry.start,entry.end]];
      if(!original&&machine===incident.machine&&record&&record.completed_at===null&&entry.start<state.now) spans=[[entry.start,state.now],[incident.estimated_repair_at,entry.end]];
      for(const [start,end] of spans) {
        const width=x(end)-x(start); if(width<=0) continue;
        svg+=`<g><title>${escapeHtml(entry.operation)} · ${start}–${end} min · ${escapeHtml(machine)}</title><rect x="${x(start)+.5}" y="${y+3}" width="${Math.max(.5,width-1)}" height="24" rx="3" fill="${color}"/>${width>32?`<text x="${x(start)+width/2}" y="${y+19}" text-anchor="middle" fill="white" font-size="9">${escapeHtml(entry.operation.split('/')[0].replace('ORD-','#'))}</text>`:''}</g>`;
      }
    }
  });
  svg+=`<line x1="${x(state.now)}" y1="15" x2="${x(state.now)}" y2="218" stroke="#344f44" stroke-width="1" stroke-dasharray="4 4"/><text x="${x(state.now)}" y="10" text-anchor="middle" fill="#344f44" font-size="9">NOW</text><text x="950" y="239" text-anchor="end" fill="#75847d" font-size="9">minutes</text></svg>`;
  return svg;
}
function renderAgent() {
  const agent=report.agent;
  if(!agent) { $('agent-result').innerHTML='<span class="pill neutral">Agent not run</span><p>Candidate comparisons are calculated by the solver and simulator. A model decision will appear here after a live run.</p>'; return; }
  $('agent-result').innerHTML=`<span class="pill">${escapeHtml(agent.decision)} · ${escapeHtml(agent.selected_policy)}</span><p class="evidence">${escapeHtml(agent.evidence_summary)}</p><p>${escapeHtml(agent.model)} · ${agent.model_requests} requests · ${agent.model_seconds.toFixed(1)}s model time</p><div class="agent-trace">${agent.trace.map(t=>`<div>${escapeHtml(t.tool)} ${t.result.policy?'· '+escapeHtml(t.result.policy):''}${t.result.error?' · rejected':''}</div>`).join('')}</div><p>Evidence summary is model-generated. Forecast metrics come from the experiment tools. Dollar cost has not yet been calculated.</p>`;
}
$('controls').addEventListener('submit',event=>{event.preventDefault();run(false);});
$('agent').addEventListener('click',()=>run(true)); $('refresh').addEventListener('click',refresh); $('provider').addEventListener('change',updateProvider);
$('download').addEventListener('click',()=>{if(!report)return;const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=`factory-recovery-${report.run_id||'run'}.json`;link.click();URL.revokeObjectURL(url);});
for(const id of ['machine','outage','repair']) $(id).addEventListener('change',()=>notice('Settings changed. Run recovery experiments to update the displayed results.'));
refresh().then(()=>run(false));
