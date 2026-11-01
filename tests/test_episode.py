import json

import pytest

from factory_lab.domain import Progress, Snapshot, check_snapshot
from factory_lab.episode import EpisodeConfig, WorldEvent, factory_observation, run_episode
from factory_lab.experiments import experiment
from factory_lab.validation import validate_plan
from test_factory import hand_plan, small_shop


def trace(repaired_at=18):
    return [WorldEvent(time=4, kind="outage", machine="A", estimated_repair_at=14,
                       uncertainty_minutes=2, source="Observed outage"),
            WorldEvent(time=8, kind="repair_estimate", machine="A", estimated_repair_at=16,
                       uncertainty_minutes=2, source="Observed estimate update"),
            WorldEvent(time=repaired_at, kind="repaired", machine="A", source="PRIVATE future repair confirmation")]


def test_confirmed_repair_controls_physics_not_forecast():
    result = run_episode(small_shop(), trace(22), policy="preserve", initial_plan=hand_plan(),
                         config=EpisodeConfig(interval_minutes=5, solve_seconds=.2))
    assert result["complete"] and not result["failures"]
    at_twenty = next(f for f in result["frames"] if f["time"] == 20)
    assert at_twenty["state"]["progress"]["one/cut"]["worked"] == 4
    assert next(m for m in at_twenty["factory"]["machines"] if m["machine"] == "A")["status"] == "down"
    final = result["frames"][-1]["state"]["progress"]
    assert final["one/cut"]["completed_at"] == 28
    assert final["one/cut"]["worked"] == 10


def test_future_information_is_absent_and_first_decision_is_identical():
    observations = []
    def inspect(scenario, state, reference, incident, history, event):
        observations.append({"state": state.model_dump(), "incident": incident.model_dump() if incident else None,
                             "assignments": [a.model_dump() for a in reference.assignments],
                             "event": event, "history": list(history)})
        candidate = experiment(scenario, state, reference, incident, "preserve", .2)
        return {"experiments": [candidate], "selected_candidate": candidate, "evidence_summary": "Protocol fixture",
                "model_requests": 0, "usage_by_request": [], "trace": [], "cost_usd": 0}
    first = []
    for actual in (18, 25):
        observations.clear()
        result = run_episode(small_shop(), trace(actual), policy="meta", supervisor=inspect,
                             initial_plan=hand_plan(), config=EpisodeConfig(interval_minutes=5, solve_seconds=.2))
        assert result["complete"]
        first.append(observations[0])
        assert "PRIVATE" not in json.dumps(observations[0])
    assert first[0] == first[1]


def test_multiple_outages_updates_and_every_frame_is_valid():
    events = trace(22) + [WorldEvent(time=6, kind="outage", machine="B", estimated_repair_at=15),
                         WorldEvent(time=13, kind="repaired", machine="B")]
    result = run_episode(small_shop(), events, policy="solver_selection", initial_plan=hand_plan(),
                         config=EpisodeConfig(interval_minutes=5, solve_seconds=.2))
    assert result["complete"] and not result["failures"]
    from factory_lab.domain import Plan
    completed = {}
    for frame in result["frames"]:
        state = Snapshot.model_validate(frame["state"])
        assert not validate_plan(small_shop(), state, Plan.model_validate(frame["plan"]))
        for op_id, record in state.progress.items():
            if op_id in completed:
                assert completed[op_id] == record
            if record.completed_at is not None:
                completed[op_id] = record


def test_failed_provider_is_reported_and_falls_back_to_valid_guard():
    def fail(*args):
        error = RuntimeError("Provider unavailable fixture")
        error.model_requests = 1
        raise error
    result = run_episode(small_shop(), trace(), policy="meta", supervisor=fail,
                         initial_plan=hand_plan(), config=EpisodeConfig(interval_minutes=5, solve_seconds=.2))
    assert result["complete"] and result["failures"]
    assert result["status"] == "completed_with_failures"
    assert result["realized_metrics"]["model_calls"] == len(result["failures"])
    assert all(f["decision"]["action"] == "FALLBACK" for f in result["frames"] if f["decision"])


def test_replay_is_deterministic_in_physical_outcomes():
    args = dict(policy="always_replan", initial_plan=hand_plan(), config=EpisodeConfig(interval_minutes=5, solve_seconds=.2))
    runs = [run_episode(small_shop(), trace(), **args) for _ in range(2)]
    assert runs[0]["frames"][-1]["state"] == runs[1]["frames"][-1]["state"]
    assert runs[0]["execution_events"] == runs[1]["execution_events"]


def test_impossible_progress_and_history_are_rejected():
    with pytest.raises(ValueError, match="elapsed"):
        check_snapshot(small_shop(), Snapshot(now=5, progress={"one/cut": Progress(machine="A", started_at=4, worked=3)}))


@pytest.mark.parametrize("policy", ["preserve", "always_replan", "fixed_interval", "solver_selection"])
def test_baselines_share_events_constraints_and_solver_budget(policy):
    config = EpisodeConfig(interval_minutes=5, solve_seconds=.2)
    result = run_episode(small_shop(), trace(), policy=policy, initial_plan=hand_plan(), config=config)
    assert result["complete"] and result["realized_metrics"]["feasibility_violations"] == 0
    assert result["configuration"] == config.model_dump()
    assert [e["kind"] for f in result["frames"] for e in f["events"] if e["kind"] != "estimate_expired"] == [e.kind for e in trace()]
