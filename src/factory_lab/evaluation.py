"""Frozen synthetic evaluation generator. Do not tune from held-out outcomes."""

import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess

from .domain import Scenario, Snapshot
from .episode import EpisodeConfig, WorldEvent, live_supervisor, run_episode
from .scenarios import load_demo
from .scheduler import solve


def generate_case_v1(seed: int) -> tuple[Scenario, list[WorldEvent]]:
    rng = random.Random(seed)
    data = load_demo().model_dump()
    data["name"] = f"Frozen synthetic evaluation v1 / seed {seed}"
    for order in data["orders"]:
        order["due"] += rng.randint(-20, 20)
        for op in order["operations"]:
            adjustment = rng.randint(-4, 6)
            op["durations"] = {m: max(1, t + adjustment) for m, t in op["durations"].items()}
    outage = rng.randint(20, 30)
    update = rng.randint(45, 60)
    estimate = rng.randint(100, 125)
    revised = max(update + 1, estimate + rng.randint(-15, 20))
    actual = max(update + 5, revised + rng.randint(-15, 15))
    second = rng.randint(75, 90)
    second_estimate = second + rng.randint(20, 40)
    second_actual = second_estimate + rng.randint(-8, 10)
    events = [WorldEvent(time=outage, kind="outage", machine="CNC-A", estimated_repair_at=estimate,
                         uncertainty_minutes=20, source="CNC-A spindle fault; current maintenance estimate supplied."),
              WorldEvent(time=update, kind="repair_estimate", machine="CNC-A", estimated_repair_at=revised,
                         uncertainty_minutes=10, source="Maintenance revises CNC-A repair estimate after inspection."),
              WorldEvent(time=actual, kind="repaired", machine="CNC-A", source="CNC-A repair confirmed."),
              WorldEvent(time=second, kind="outage", machine="INSPECT", estimated_repair_at=second_estimate,
                         uncertainty_minutes=10, source="Inspection fixture fault; maintenance estimate supplied."),
              WorldEvent(time=second_actual, kind="repaired", machine="INSPECT", source="Inspection fixture repair confirmed.")]
    return Scenario.model_validate(data), sorted(events, key=lambda event: event.time)


def evaluate(config_path: Path, output: Path, *, include_meta: bool = False) -> dict:
    raw = config_path.read_bytes()
    contract = json.loads(raw)
    config = EpisodeConfig.model_validate(contract["episode_config"])
    source_revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in contract["seeds"]:
        scenario, events = generate_case_v1(seed)
        initial = solve(scenario, Snapshot(), time_limit=config.solve_seconds)
        policies = list(contract["baseline_policies"])
        if include_meta and seed in contract["planned_meta_subset"]:
            policies.append("meta")
        for policy in policies:
            artifact = output / f"{seed}-{policy}.json"
            if artifact.exists():
                # Expensive runs resume only from an exact configuration/revision.
                result = json.loads(artifact.read_text())
                if result.get("config_sha256") != hashlib.sha256(raw).hexdigest() or result.get("source_revision") != source_revision:
                    raise ValueError("Existing evaluation artifact belongs to another config/revision; use a new output directory")
            else:
                try:
                    result = run_episode(scenario, events, policy=policy, config=config, initial_plan=initial,
                        supervisor=live_supervisor(solve_seconds=config.solve_seconds) if policy == "meta" else None)
                except (ValueError, RuntimeError) as error:
                    result = {"status": "failed", "complete": False, "realized_metrics": None,
                              "failures": [{"error": str(error).split("\n")[0][:250]}]}
                result.update(seed=seed, source_revision=source_revision, config_sha256=hashlib.sha256(raw).hexdigest())
                artifact.write_text(json.dumps(result, indent=2) + "\n")
            rows.append({"seed": seed, "policy": policy, "status": result["status"],
                         "metrics": result["realized_metrics"], "failures": result["failures"], "artifact": artifact.name})
            print(f"seed {seed} / {policy}: {result['status']}", flush=True)
    aggregate = {}
    metric_keys = ["weighted_tardiness_minutes", "on_time_orders", "rerouted_operations", "queued_start_shift_minutes",
                   "revision_count", "guard_solver_seconds", "experiment_solver_seconds", "model_calls", "wall_seconds"]
    for policy in [*contract["baseline_policies"], "meta"]:
        attempts = [r for r in rows if r["policy"] == policy]
        complete = [r for r in attempts if r["metrics"] is not None]
        aggregate[policy] = {"attempted": len(attempts), "completed": len(complete),
            "failed_or_fallback": sum(r["status"] != "completed" for r in attempts),
            "metrics": {key: {"mean": statistics.mean(r["metrics"][key] for r in complete),
                              "std": statistics.pstdev(r["metrics"][key] for r in complete),
                              "min": min(r["metrics"][key] for r in complete),
                              "max": max(r["metrics"][key] for r in complete)} for key in metric_keys} if complete else {}}
    meta_seeds = [r["seed"] for r in rows if r["policy"] == "meta"]
    paired = [r for r in rows if r["seed"] in meta_seeds]
    summary = {"kind": "frozen_synthetic_evaluation", "source_revision": source_revision,
               "config_sha256": hashlib.sha256(raw).hexdigest(), "configuration": contract,
               "rows": rows, "aggregate": aggregate, "meta_paired_rows": paired,
               "limitations": ["Synthetic cases; no factory telemetry or industrial validation.",
                   "Meta coverage is a predeclared subset, not all 20 cases.",
                   "Fallback results remain labelled and are not successful autonomous decisions.",
                   "Wall-clock-bounded CP-SAT schedules can vary across hosts."]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
