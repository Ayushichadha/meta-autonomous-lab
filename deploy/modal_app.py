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
              scaledown_window=600, timeout=900, volumes={'/state':volume},
              secrets=[modal.Secret.from_name('factory-meta')])
@modal.concurrent(max_inputs=20)
@modal.web_server(8000, startup_timeout=60)
def web():
    import os
    import subprocess
    # Runs and the $1 admission ledger survive container restarts. Reservations
    # commit before inference; failure to persist prevents the request.
    Path('/state/runs').mkdir(exist_ok=True)
    if not Path('/app/runs').exists():
        Path('/app/runs').symlink_to('/state/runs', target_is_directory=True)
    env = {**os.environ, 'PYTHONPATH':'/app/src',
           'FACTORY_MODAL_VOLUME':'factory-recovery-state'}
    from urllib.parse import urlsplit
    host = urlsplit(modal.Function.from_name('factory-recovery-lab', 'web').get_web_url()).netloc
    env['FACTORY_PUBLIC_HOST'] = host
    code = ('from factory_lab.server import run_dashboard; '
            'import os; run_dashboard(8000, bind="0.0.0.0", '
            'public_host=os.environ["FACTORY_PUBLIC_HOST"])')
    subprocess.Popen(['python','-c',code], cwd='/app', env=env)
