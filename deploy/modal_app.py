"""CPU-only hosted factory demo. Deploy with: modal deploy deploy/modal_app.py."""
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parents[1]
app = modal.App('factory-recovery-lab')
volume = modal.Volume.from_name('factory-recovery-state', create_if_missing=True)
image = (modal.Image.debian_slim(python_version='3.12')
         .pip_install('ortools>=9.12,<10', 'simpy>=4.1,<5', 'pydantic>=2.10,<3',
                      'httpx>=0.28,<1', 'python-dotenv>=1,<2', 'modal>=1,<2')
         .add_local_dir(ROOT/'src', '/app/src')
         .add_local_dir(ROOT/'results', '/app/results'))


@app.function(image=image, cpu=1, memory=1024, max_containers=1,
              scaledown_window=60, timeout=900, volumes={'/state':volume},
              secrets=[modal.Secret.from_name('factory-meta')])
def execute(job_id, kind, payload):
    import os
    import sys
    os.chdir('/app'); sys.path.insert(0,'/app/src')
    volume.reload()
    Path('/state/runs').mkdir(exist_ok=True)
    if not Path('/app/runs').exists():
        Path('/app/runs').symlink_to('/state/runs',target_is_directory=True)
    os.environ['FACTORY_MODAL_VOLUME']='factory-recovery-state'
    from factory_lab.cloud import execute as run
    run(job_id,kind,payload)


@app.function(image=image, cpu=.25, memory=512, max_containers=1,
              scaledown_window=60, timeout=900)
@modal.concurrent(max_inputs=20)
@modal.web_server(8000, startup_timeout=60)
def web():
    import os
    import subprocess
    from urllib.parse import urlsplit
    host=urlsplit(modal.Function.from_name('factory-recovery-lab','web').get_web_url()).netloc
    env={**os.environ,'PYTHONPATH':'/app/src','FACTORY_CLOUD_JOBS':'1','FACTORY_PUBLIC_HOST':host}
    code=('from factory_lab.server import run_dashboard; import os; '
          'run_dashboard(8000,bind="0.0.0.0",public_host=os.environ["FACTORY_PUBLIC_HOST"])')
    subprocess.Popen(['python','-c',code],cwd='/app',env=env)
