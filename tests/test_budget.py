import pytest

from factory_lab.budget import BudgetLedger, usage_cost


def test_usage_cost_counts_cached_input_and_all_output():
    assert usage_cost("muse-spark-1.3", {"prompt_tokens": 1000, "completion_tokens": 100,
                      "prompt_tokens_details": {"cached_tokens": 200}}) == pytest.approx(.001455)
    assert usage_cost("muse-spark-1.3", {}) is None


def test_ledger_enforces_limit_across_clients_and_releases_unused_reservation(tmp_path):
    path = tmp_path / "usage.jsonl"
    first = BudgetLedger(path, limit_usd=.02)
    request = first.reserve("muse-spark-1.3", .015)
    with pytest.raises(RuntimeError, match="no request sent"):
        BudgetLedger(path, limit_usd=.02).reserve("muse-spark-1.3", .01)
    first.settle(request, "muse-spark-1.3", {"prompt_tokens": 100, "completion_tokens": 100})
    BudgetLedger(path, limit_usd=.02).reserve("muse-spark-1.3", .01)


def test_unknown_usage_keeps_reservation(tmp_path):
    ledger = BudgetLedger(tmp_path / "usage.jsonl", limit_usd=.01)
    request = ledger.reserve("muse-spark-1.3", .009)
    assert ledger.settle(request, "muse-spark-1.3", {}) is None
    with pytest.raises(RuntimeError):
        ledger.reserve("muse-spark-1.3", .002)


def test_provider_refuses_unsupported_choices_and_excess_requests_without_network(monkeypatch, tmp_path):
    from factory_lab.provider import ModelClient, ProviderError
    monkeypatch.setenv("META_API_KEY", "test-only-not-a-real-key")
    client = ModelClient("meta", env_file=str(tmp_path / "absent.env"))
    client.ledger = BudgetLedger(tmp_path / "usage.jsonl")
    sent = []
    def reply(method, path, payload):
        sent.append(payload)
        return {"choices": [{"message": {"role": "assistant", "content": "fixture"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10}}
    monkeypatch.setattr(client, "_request", reply)
    with pytest.raises(ValueError, match="automatic tool choice"):
        client.complete([], [], tool_choice="required")
    assert not sent
    for _ in range(6):
        client.complete([], [])
    with pytest.raises(ProviderError, match="request limit"):
        client.complete([], [])
    assert len(sent) == 6
    assert all(p["max_tokens"] == 1024 and p["reasoning_effort"] == "low" for p in sent)
