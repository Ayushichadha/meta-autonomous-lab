"""Protocol fixtures validate boundaries, not real model capability."""

import json

import pytest

from factory_lab.agent import supervise
from factory_lab.domain import Incident, Snapshot, apply_incident
from factory_lab.provider import ModelClient, ProviderError
from factory_lab.simulator import simulate
from test_factory import hand_plan, small_shop


class ScriptedClient:
    provider = "protocol-fixture"
    model = "not-a-real-model"

    def __init__(self, calls):
        self.calls = iter(calls)

    def complete(self, messages, tools):
        name, arguments = next(self.calls)
        return {"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "fixture", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}, "seconds": .01}


def context():
    scenario, original = small_shop(), hand_plan()
    state = simulate(scenario, Snapshot(), original, until=4).snapshot
    incident = Incident(machine="A", observed_at=4, estimated_repair_at=14, source="Fixture")
    return scenario, apply_incident(scenario, state, incident), original, incident


def test_agent_requires_tested_candidate_before_selection():
    client = ScriptedClient([
        ("select_plan", {"policy": "reroute", "evidence_summary": "Untested"}),
        ("run_experiment", {"policy": "preserve"}),
        ("select_plan", {"policy": "preserve", "evidence_summary": "Fixture evidence"}),
    ])
    result = supervise(client, *context(), time_limit=.2)
    assert result["decision"] == "PERSIST"
    assert len(result["experiments"]) == 1
    assert result["trace"][0]["result"]["error"] == "Invalid tool request"
    assert result["model_requests"] == 3


def test_agent_cannot_skip_baseline_or_execute_unknown_tool():
    client = ScriptedClient([
        ("run_experiment", {"policy": "reroute"}),
        ("run_shell", {"command": "untrusted"}),
        ("run_experiment", {"policy": "preserve"}),
        ("run_experiment", {"policy": "preserve"}),
        ("select_plan", {"policy": "preserve", "evidence_summary": "Fixture evidence"}),
    ])
    result = supervise(client, *context(), time_limit=.2)
    assert len(result["experiments"]) == 1
    assert result["trace"][0]["result"]["error"]
    assert result["trace"][1]["result"]["error"]


def test_agent_stops_at_request_budget_without_selecting():
    client = ScriptedClient([("unknown", {})] * 6)
    with pytest.raises(RuntimeError, match="six model requests"):
        supervise(client, *context(), time_limit=.2)


def test_provider_reports_missing_key_without_network(monkeypatch, tmp_path):
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="No baseten API key"):
        ModelClient(env_file=str(tmp_path / "absent.env"))
