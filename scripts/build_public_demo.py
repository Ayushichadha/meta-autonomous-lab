"""Build an allowlisted public replay. No backend, environment, or credentials."""

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def build(destination: Path) -> None:
    values = {
        "data/status.json": {"read_only": True, "providers": {"meta": {"configured": False}, "baseten": {"configured": False}}, "budget": None},
        "data/episode.json": {"mode": "recorded", "episode": json.loads((ROOT/"results/demo/meta-sequential-demo.json").read_text())},
        "data/note.json": json.loads((ROOT/"results/notes/verified-note-workflow.json").read_text()),
        "data/evaluation.json": json.loads((ROOT/"results/evaluation-v2/summary.json").read_text()),
    }
    web = ROOT/"src/factory_lab/web"
    html = (web/"console.html").read_text().replace('<meta charset="utf-8">', '<meta charset="utf-8"><meta name="factory-demo-mode" content="public-replay">')
    html = html.replace('href="/console.css"','href="./console.css"').replace('src="/console.js"','src="./console.js"').replace('href="/"','href="./"')
    html = html.replace('href="/single"','href="https://ayushichadha--factory-recovery-lab-web.us-east.modal.run/"').replace('Single-event lab','Open live app')
    files = {"index.html":html.encode(), "console.css":(web/"console.css").read_bytes(),
             "console.js":(web/"console.js").read_bytes(), ".nojekyll":b""}
    files.update({name:(json.dumps(value)+"\n").encode() for name,value in values.items()})
    destination.mkdir(parents=True,exist_ok=True)
    unexpected = [p for p in destination.rglob('*') if p.is_file() and str(p.relative_to(destination)) not in files]
    if unexpected:
        raise ValueError("Unexpected files in the public output directory; refusing to publish")
    for name,payload in files.items():
        if re.search(rb"LLM_[0-9]+_[A-Za-z0-9_-]+",payload):
            raise ValueError("Credential-like value detected in public artifact")
        path=destination/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payload)
    print(f"Built {len(files)} allowlisted files in {destination}; public replay has no backend or credentials.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'build/public-replay')
    build(parser.parse_args().output)
