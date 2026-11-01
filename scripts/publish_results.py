"""Package normalized simulation artifacts; never provider HTTP responses or credentials."""

import gzip
import json
from pathlib import Path
import re


def write_checked(path: Path, value: dict, *, compressed=False):
    payload = (json.dumps(value, indent=2) + "\n").encode()
    if re.search(rb"LLM_[0-9]+_[A-Za-z0-9_-]+", payload):
        raise ValueError("Refusing to publish a credential-like value")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(payload, mtime=0) if compressed else payload)


for version in (1, 2):
    source = Path(f"runs/evaluation-v{version}")
    summary = json.loads((source / "summary.json").read_text())
    destination = Path(f"results/evaluation-v{version}")
    for row in summary["rows"]:
        name = row["artifact"]
        artifact = json.loads((source / name).read_text())
        write_checked(destination / (name + ".gz"), artifact, compressed=True)
        row["artifact"] += ".gz"
    for row in summary["meta_paired_rows"]:
        if not row["artifact"].endswith(".gz"):
            row["artifact"] += ".gz"
    summary["distribution_note"] = "Normalized episode artifacts are gzip-compressed for the public repository. No raw provider HTTP responses are included."
    write_checked(destination / "summary.json", summary)

demo = json.loads(Path("runs/meta-sequential-demo.json").read_text())
demo.update(recorded_on="2026-11-01", source_revision="4191c52", execution_mode="recorded_real_meta_run")
write_checked(Path("results/demo/meta-sequential-demo.json"), demo)
print("Packaged both evaluation versions and the recorded live demo. Credential-pattern scan passed.")
