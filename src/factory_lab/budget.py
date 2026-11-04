"""Local estimated-dollar guard; not a provider-side billing limit.

Reservations remain charged locally when a timed-out/failed call has unknown usage.
No prompts, responses, or credentials are stored in this ledger.
"""

from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
from uuid import uuid4

PRICING_SOURCE = "https://dev.meta.ai/docs/pricing-rate-limits"
PRICING_CHECKED = "2026-11-01"


def configured_limit() -> float:
    value = float(os.getenv("FACTORY_META_LIMIT_USD", "1"))
    if not math.isfinite(value) or not 0 < value <= 3:
        raise ValueError("Configured Meta allowance must be positive and at most $3")
    return value


def rates(model: str) -> tuple[float, float, float]:
    if model in {"muse-spark-1.1", "muse-spark-1.2", "muse-spark-1.3"}:
        return 1.25, .15, 4.25
    if model == "muse-wonder-1.0":
        return 4.0, .20, 20.0
    raise ValueError("No verified price table for this model; refuse unbudgeted inference")


def usage_cost(model: str, usage: dict) -> float | None:
    if model == "muse-voice-transcribe-1.0":
        duration = usage.get("audioDurationMs")
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            return None
        return math.floor(duration / 1000) * .18 / 3600
    prompt = usage.get("prompt_tokens", usage.get("input_tokens"))
    output = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(prompt, int) or not isinstance(output, int) or min(prompt, output) < 0:
        return None
    details = usage.get("prompt_tokens_details", usage.get("input_tokens_details", {})) or {}
    cached = min(prompt, max(0, details.get("cached_tokens", 0)))
    input_rate, cached_rate, output_rate = rates(model)
    return ((prompt - cached) * input_rate + cached * cached_rate + output * output_rate) / 1e6


class BudgetLedger:
    def __init__(self, path: str | Path = "runs/meta-usage.jsonl", limit_usd: float = 1.0):
        if not math.isfinite(limit_usd) or limit_usd <= 0:
            raise ValueError("Budget must be a positive finite amount")
        self.path = Path(path)
        self.limit_usd = limit_usd

    @contextmanager
    def locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+", encoding="utf-8") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                stream.seek(0)
                records = [json.loads(line) for line in stream if line.strip()]
                yield stream, records
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def reserve(self, model: str, amount: float) -> str:
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Reservation must be positive and finite")
        with self.locked() as (stream, records):
            charges = {}
            for item in records:
                charges[item["request_id"]] = item["charged_usd"]
            if sum(charges.values()) + amount > self.limit_usd:
                raise RuntimeError(f"Local Meta credit guard reached its ${self.limit_usd:g} development allowance; no request sent")
            request_id = uuid4().hex
            stream.write(json.dumps({"request_id": request_id, "model": model, "status": "reserved",
                                     "charged_usd": amount, "pricing_checked": PRICING_CHECKED}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            if os.getenv("FACTORY_MODAL_VOLUME"):
                import modal
                modal.Volume.from_name(os.environ["FACTORY_MODAL_VOLUME"]).commit()
            return request_id

    def settle(self, request_id: str, model: str, usage: dict) -> float | None:
        cost = usage_cost(model, usage)
        if cost is None:
            return None  # Keep the conservative reservation.
        with self.locked() as (stream, _):
            stream.write(json.dumps({"request_id": request_id, "model": model, "status": "usage_reported",
                                     "charged_usd": cost, "usage": usage,
                                     "pricing_checked": PRICING_CHECKED}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            if os.getenv("FACTORY_MODAL_VOLUME"):
                import modal
                modal.Volume.from_name(os.environ["FACTORY_MODAL_VOLUME"]).commit()
        return cost
