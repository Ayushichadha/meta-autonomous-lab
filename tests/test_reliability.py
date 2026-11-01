import gzip
import json
from pathlib import Path

import httpx
import pytest

from factory_lab.agent import supervise
from factory_lab.budget import BudgetLedger
from factory_lab.domain import Incident, Progress, Snapshot, apply_incident, check_snapshot
from factory_lab.provider import ModelClient, ProviderError
from factory_lab.scheduler import solve
from factory_lab.simulator import simulate
from test_agent import ScriptedClient, context
from test_factory import hand_plan, small_shop


def test_preloaded_baseline_allows_persist_in_one_request():
    client = ScriptedClient([("select_plan", {"policy": "preserve", "evidence_summary": "No additional experiment justified."})])
    result = supervise(client, *context(), time_limit=.2)
    assert result["model_requests"] == 1
    assert result["trace"][0]["origin"] == "mandatory_baseline"
    assert result["decision"] == "PERSIST"


def test_malformed_tool_arguments_are_recorded_without_crashing():
    client = ScriptedClient([("select_plan", {"policy": "preserve", "evidence_summary": "Select measured baseline."})])
    original = client.complete
    first = True
    def complete(messages, tools):
        nonlocal first
        if first:
            first = False
            return {"message": {"tool_calls": [{"id": "bad", "function": {"name": "run_experiment", "arguments": "{"}}]}}
        return original(messages, tools)
    client.complete = complete
    result = supervise(client, *context(), time_limit=.2)
    assert any(t["result"].get("error") for t in result["trace"])


def test_inspection_is_current_and_rejects_unknown_machine():
    client = ScriptedClient([("inspect_factory", {"focus_machine": "does-not-exist"}),
                             ("inspect_factory", {"focus_machine": "A"}),
                             ("select_plan", {"policy": "preserve", "evidence_summary": "Validated baseline."})])
    result = supervise(client, *context(), time_limit=.2)
    inspected = next(t["result"] for t in result["trace"] if t["tool"] == "inspect_factory" and "machines" in t["result"])
    assert inspected["time"] == 4
    assert len(inspected["machines"]) == 1 and inspected["machines"][0]["status"] == "down"
    assert "future_events" not in inspected


def test_delayed_queue_cannot_be_overtaken_without_rescheduling():
    scenario, original = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), original, until=4).snapshot
    state = apply_incident(scenario, state, Incident(machine="A", observed_at=4, estimated_repair_at=30, source="Fixture"))
    plan = solve(scenario, state, reference=original, policy="preserve", time_limit=.2)
    result = simulate(scenario, state, plan, repair_overrides={"A": 35}).snapshot
    assert result.progress["two/check"].started_at >= result.progress["one/check"].completed_at


def test_overlapping_historical_occupancy_is_rejected():
    state = Snapshot(now=15, progress={
        "one/cut": Progress(machine="A", started_at=0, worked=10, completed_at=10),
        "two/cut": Progress(machine="A", started_at=4, worked=8, completed_at=12)})
    with pytest.raises(ValueError, match="occupancy overlaps"):
        check_snapshot(small_shop(), state)


def test_failed_network_call_is_not_retried_and_keeps_reservation(monkeypatch, tmp_path):
    monkeypatch.setenv("META_API_KEY", "fixture-key-not-real")
    client = ModelClient(env_file=str(tmp_path / "absent.env"))
    client.ledger = BudgetLedger(tmp_path / "ledger.jsonl")
    calls = []
    def fail(*args):
        calls.append(1)
        raise ProviderError("Fixture network failure")
    monkeypatch.setattr(client, "_request", fail)
    with pytest.raises(ProviderError):
        client.complete([], [])
    assert len(calls) == 1
    records = [json.loads(line) for line in client.ledger.path.read_text().splitlines()]
    assert len(records) == 1 and records[0]["status"] == "reserved"


def test_provider_error_redacts_echoed_key(monkeypatch, tmp_path):
    key = "fixture-key-not-real"
    monkeypatch.setenv("META_API_KEY", key)
    client = ModelClient(env_file=str(tmp_path / "absent.env"))
    original = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={"error": {"message": "Echo: " + key}}))
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(ProviderError) as error:
        client.models()
    assert key not in str(error.value) and "[redacted]" in str(error.value)


def test_published_artifacts_match_all_summary_rows():
    root = Path(__file__).resolve().parents[1]
    for version in (1, 2):
        folder = root / "results" / f"evaluation-v{version}"
        summary = json.loads((folder / "summary.json").read_text())
        assert len(summary["configuration"]["seeds"]) == 20
        assert len(summary["rows"]) == 83
        for row in summary["rows"]:
            with gzip.open(folder / row["artifact"], "rt") as stream:
                artifact = json.load(stream)
            assert artifact["seed"] == row["seed"]
            assert artifact["status"] == row["status"]
            assert artifact["realized_metrics"] == row["metrics"]
            assert artifact["source_revision"] == summary["source_revision"]
