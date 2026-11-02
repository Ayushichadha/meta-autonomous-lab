"""Branch a recorded observation without rewriting its history or inventing repairs."""

from .domain import Plan, Scenario, Snapshot
from .episode import EpisodeConfig, WorldEvent, live_supervisor, run_episode
from .notes import NoteExtraction, validate_extraction


def branch_context(source: dict, frame_index: int):
    if not 0 <= frame_index < len(source["frames"]):
        raise ValueError("Unknown source observation")
    frame = source["frames"][frame_index]
    return (Scenario.model_validate(source["scenario"]), Snapshot.model_validate(frame["state"]),
            Plan.model_validate(frame["plan"]))


def run_note_branch(source: dict, frame_index: int, interpretation: dict, *, policy="solver_selection",
                    provider="meta", on_frame=None, on_progress=None) -> dict:
    scenario, state, reference = branch_context(source, frame_index)
    # Revalidate stored claims against the exact starting observation; clients
    # cannot authorize an update by posting a forged 'validated' status.
    checked = validate_extraction(interpretation["note"], scenario, state,
                                 NoteExtraction.model_validate(interpretation["proposed_claims"]))
    if checked["status"] != "validated" or not checked["events"]:
        raise ValueError("No fully validated state-changing maintenance event to apply")
    if policy not in {"solver_selection", "meta"}:
        raise ValueError("Note branches support the strong conventional selector or Meta supervisor")
    updates = [WorldEvent.model_validate(e) for e in checked["events"]]
    future = [WorldEvent.model_validate(e) for e in source["private_trace_released_after_execution"] if e["time"] > state.now]
    down = set(state.available_at)
    accepted, superseded = [], []
    for event in updates + future:
        obsolete = ((event.kind == "outage" and event.machine in down) or
                    (event.kind != "outage" and event.machine not in down))
        if obsolete:
            superseded.append(event.model_dump())
            continue
        accepted.append(event)
        if event.kind == "outage":
            down.add(event.machine)
        elif event.kind == "repaired":
            down.remove(event.machine)
    if down:
        raise ValueError("The branch has no confirmed future repair scenario for " + ", ".join(sorted(down)) +
                         ". An estimate cannot be substituted for a physical repair; realized execution was not run.")
    config = EpisodeConfig()
    result = run_episode(scenario, accepted, policy=policy, config=config, starting_state=state,
                         initial_plan=reference, on_frame=on_frame,
                         supervisor=live_supervisor(provider, solve_seconds=config.solve_seconds,
                                                    on_progress=on_progress) if policy == "meta" else None)
    result["branch"] = {"source_observation_index": frame_index, "source_time": state.now,
                        "source_policy": source["policy"], "note": interpretation["note"],
                        "validated_update": checked, "interpretation_model": interpretation.get("model"),
                        "interpretation_cost_usd": interpretation.get("estimated_cost_usd"),
                        "superseded_events_released_after_execution": superseded,
                        "original_recording_unchanged": True,
                        "metric_scope": "Outcome delays cover all orders; revision and model-use counters cover the branch only."}
    # Historical observations are copied, not re-executed or modified. Their
    # decisions are labelled as source history and excluded from branch counters.
    prefix = []
    for frame in source["frames"][:frame_index]:
        prefix.append({**frame, "source_history": True})
    result["frames"] = prefix + result["frames"]
    result["kind"] = "maintenance_note_branch"
    return result
