"""Detached Modal jobs; web requests never own a long-running execution."""
import json
import time
from uuid import uuid4


def store():
    import modal
    return modal.Dict.from_name('factory-recovery-jobs', create_if_missing=True)


def start(kind, payload):
    import modal
    jobs = store()
    previous = jobs.get('active')
    if previous and previous['expires'] < time.time():
        jobs.pop('active', None)
    job_id = uuid4().hex[:16]
    if not jobs.put('active', {'id': job_id, 'expires': time.time()+960}, skip_if_exists=True):
        raise ValueError('A hosted execution is already running. Please wait for it to finish.')
    jobs[job_id] = {'job_id':job_id,'status':'running','frames':[], 'progress':[],
                    'scenario':payload['scenario'],'policy':payload['policy']}
    try:
        modal.Function.from_name('factory-recovery-lab','execute').spawn(job_id,kind,payload)
    except Exception:
        jobs[job_id]={**jobs[job_id], 'status':'failed', 'error':'Cloud dispatch failed; no model request was sent.'}
        jobs.pop('active',None)
        raise
    return job_id


def get(job_id):
    return store().get(job_id)


def execute(job_id, kind, payload):
    from pathlib import Path
    from .episode import run_episode, EpisodeConfig, demo_events, live_supervisor
    from .domain import Scenario
    jobs=store(); record=jobs[job_id]
    def progress(item):
        record['progress']=(record['progress']+[item])[-100:]
        jobs[job_id]=record
    def frame(item):
        record['frames'].append(item)
        jobs[job_id]=record
    try:
        if kind=='branch':
            from .branching import run_note_branch
            source=payload['record']
            result=run_note_branch(source['source'],source['frame_index'],source['interpretation'],
                policy=payload['policy'],on_frame=frame,on_progress=progress)
        else:
            cfg=EpisodeConfig()
            result=run_episode(Scenario.model_validate(payload['scenario']),demo_events(),
                policy=payload['policy'], config=cfg, on_frame=frame,
                supervisor=live_supervisor('meta',solve_seconds=cfg.solve_seconds,on_progress=progress)
                if payload['policy']=='meta' else None)
        result['run_id']=job_id
        Path('runs').mkdir(exist_ok=True)
        Path('runs',job_id+'-episode.json').write_text(json.dumps(result))
        import modal
        modal.Volume.from_name('factory-recovery-state').commit()
        record.update(status='completed',result=result)
    except Exception as error:
        record.update(status='failed',error=str(error).split('\n')[0][:250])
    finally:
        jobs[job_id]=record
        if jobs.get('active',{}).get('id')==job_id:
            jobs.pop('active',None)
