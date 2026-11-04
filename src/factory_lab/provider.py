"""Small explicit provider boundary. No credentials or raw HTTP errors are logged."""

import os
import json
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv

from .budget import BudgetLedger, rates, configured_limit


class ProviderError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, provider: str = "meta", *, env_file: str = ".env"):
        load_dotenv(Path(env_file), override=False)
        self.provider = provider
        if provider == "baseten":
            self.base_url = "https://inference.baseten.co/v1"
            self.model = os.getenv("BASETEN_MODEL", "meta-models/muse-spark-open-1026")
            key = os.getenv("BASETEN_API_KEY")
        elif provider == "meta":
            self.base_url = "https://api.meta.ai/v1"
            self.model = os.getenv("META_MODEL", "muse-spark-1.3")
            key = os.getenv("META_API_KEY") or os.getenv("MODEL_API_KEY")
        else:
            raise ValueError("Provider must be baseten or meta")
        if not key or not key.strip():
            raise ProviderError(f"No {provider} API key configured. Add it to the local .env file; never paste it into logs.")
        self._key = key.strip()
        self.requests = 0
        self.cost_usd = 0.0
        self.ledger = BudgetLedger(limit_usd=configured_limit()) if provider == "meta" else None

    def _request(self, method: str, path: str, payload=None, *, files=None) -> dict:
        try:
            with httpx.Client(timeout=60.0, follow_redirects=False) as client:
                response = client.request(method, self.base_url + path,
                    headers={"Authorization": "Bearer " + self._key}, json=payload, files=files)
        except httpx.RequestError:
            raise ProviderError(f"{self.provider} network request failed; check connectivity and try again.") from None
        if response.status_code >= 300:
            # Read only the bounded error message and remove any echoed key.
            try:
                error = response.json().get("error", {})
                detail = str(error.get("message", "")) if isinstance(error, dict) else ""
            except (ValueError, AttributeError):
                detail = ""
            detail = detail.replace(self._key, "[redacted]")[:250]
            raise ProviderError(f"{self.provider} returned HTTP {response.status_code}. {detail or 'Check credentials, model access, rate limits, and provider status.'}")
        try:
            return response.json()
        except ValueError:
            raise ProviderError("Provider returned a non-JSON response") from None

    def transcribe_audio(self, data_url: str) -> dict:
        from .voice import validate_audio
        if self.provider != "meta" or self.ledger is None:
            raise ProviderError("Maintenance dictation requires Meta API")
        raw, duration, digest = validate_audio(data_url)
        if self.requests >= 6:
            raise ProviderError("Model request limit reached; no request sent")
        model = "muse-voice-transcribe-1.0"
        request_id = self.ledger.reserve(model, max(.00005, (int(duration)+2) * .18 / 3600))
        self.requests += 1
        started = perf_counter()
        settings = {"model":model,"mode":"PUSH_TO_TALK","audioEncoding":"WAV",
                    "languageBias":["English"],"keywords":["CNC-A","CNC-B","INSPECT","ASSEMBLY"]}
        data = self._request("POST", "/asr/transcribe", files={
            "request":(None,json.dumps(settings),"application/json"),
            "audio":("maintenance.wav",raw,"audio/wav")})
        transcript = data.get("transcript")
        if not isinstance(transcript,str) or not transcript.strip() or len(transcript)>2000:
            raise ProviderError("No usable bounded transcript returned; no update applied")
        processed = data.get("audioDurationMs")
        if not isinstance(processed,(float,int)) or not 0 <= processed <= duration*1000+1000:
            processed = None
        cost = self.ledger.settle(request_id,model,{"audioDurationMs":processed})
        return {"transcription":transcript,"model":model,"review_required":True,"state_changed":False,
                "audio_sha256":digest,"duration_seconds":duration,"processed_audio_ms":processed,
                "estimated_cost_usd":cost,"seconds":perf_counter()-started}

    def models(self) -> list[str]:
        return [m["id"] for m in self._request("GET", "/models").get("data", []) if "id" in m]

    def complete(self, messages: list[dict], tools: list[dict], *, max_tokens: int = 1024,
                 tool_choice="auto", reasoning_effort: str = "low") -> dict:
        if self.provider == "meta" and tool_choice != "auto":
            raise ValueError("Meta API supports only automatic tool choice; no request sent")
        if self.requests >= 6:
            raise ProviderError("Model request limit reached; no request sent")
        if not 1 <= max_tokens <= 2048:
            raise ValueError("Output cap must be between 1 and 2048 tokens")
        # Image bytes are not text tokens. Bound and validate one image separately,
        # then reserve a conservative visual-token allowance in addition to text.
        accounting_messages = json.loads(json.dumps(messages))
        image_count = 0
        for message in accounting_messages:
            if isinstance(message.get("content"), list):
                for part in message["content"]:
                    if part.get("type") == "image_url":
                        from .vision import validate_image
                        validate_image(part.get("image_url", {}).get("url", ""))
                        image_count += 1
                        part["image_url"]["url"] = "[bounded image]"
        if image_count > 1:
            raise ProviderError("Only one bounded image is supported per request")
        input_bytes = len(json.dumps({"messages": accounting_messages, "tools": tools}, ensure_ascii=True).encode())
        if input_bytes > 60000:
            raise ProviderError("Prompt exceeded the local size limit; no request sent")
        request_id = None
        if self.ledger:
            input_rate, _, output_rate = rates(self.model)
            # Byte count plus overhead is deliberately conservative; this is an
            # application estimate, not a token-counting or billing guarantee.
            reserve = ((input_bytes + 4096 + image_count * 32768) * input_rate + max_tokens * output_rate) / 1e6
            request_id = self.ledger.reserve(self.model, reserve)
        self.requests += 1
        start = perf_counter()
        payload = {
            "model": self.model, "messages": messages, "tools": tools,
            "tool_choice": tool_choice, "max_tokens": max_tokens,
        }
        if self.provider == "meta":
            payload["reasoning_effort"] = reasoning_effort
        data = self._request("POST", "/chat/completions", payload)
        cost = self.ledger.settle(request_id, self.model, data.get("usage", {})) if self.ledger else None
        if cost is not None:
            if self.cost_usd is not None:
                self.cost_usd += cost
        else:
            self.cost_usd = None
        try:
            choice = data["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("Provider response has no usable assistant message") from None
        if message.get("refusal"):
            raise ProviderError("Model declined the request")
        if choice.get("finish_reason") == "length":
            raise ProviderError("Model output hit its token cap; no incomplete decision was applied")
        return {"message": message, "usage": data.get("usage", {}),
                "seconds": perf_counter() - start, "model": data.get("model", self.model),
                "estimated_cost_usd": cost}
