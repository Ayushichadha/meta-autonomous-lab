import importlib.util
import json
from pathlib import Path

import pytest


def builder():
    path = Path(__file__).resolve().parents[1] / 'scripts/build_public_demo.py'
    spec = importlib.util.spec_from_file_location('public_demo', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_public_build_only_publishes_replay_assets(tmp_path):
    builder().build(tmp_path)
    files = {str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*') if p.is_file()}
    assert files == {'index.html', 'console.css', 'console.js', '.nojekyll',
                     'data/status.json', 'data/episode.json', 'data/note.json', 'data/evaluation.json'}
    html = (tmp_path/'index.html').read_text()
    assert 'content="public-replay"' in html
    assert 'src="./console.js"' in html
    assert json.loads((tmp_path/'data/status.json').read_text())['read_only'] is True
    note = json.loads((tmp_path/'data/note.json').read_text())
    assert note['interpretation']['status'] == 'validated'


def test_public_build_refuses_unexpected_files(tmp_path):
    (tmp_path/'.env').write_text('not a credential')
    with pytest.raises(ValueError, match='Unexpected files'):
        builder().build(tmp_path)
    assert not (tmp_path/'index.html').exists()
