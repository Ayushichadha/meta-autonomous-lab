"""Small explicit provider boundary. No credentials or raw HTTP errors are logged."""

import os
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv


class ProviderError(RuntimeError):
    pass


class ModelClient:
    def __init__(self, provider: str = "baseten", *, env_file: str = ".env"):
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

    def _request(self, method: str, path: str, payload=None) -> dict:
        try:
            with httpx.Client(timeout=60.0, follow_redirects=False) as client:
                response = client.request(method, self.base_url + path,
                    headers={"Authorization": "Bearer " + self._key}, json=payload)
        except httpx.RequestError:
            raise ProviderError(f"{self.provider} network request failed; check connectivity and try again.") from None
        if response.status_code >= 300:
            # Raw provider bodies can echo request material; keep errors bounded.
            raise ProviderError(f"{self.provider} returned HTTP {response.status_code}. Check credentials, model access, rate limits, and provider status.")
        try:
            return response.json()
        except ValueError:
            raise ProviderError("Provider returned a non-JSON response") from None

    def models(self) -> list[str]:
        return [m["id"] for m in self._request("GET", "/models").get("data", []) if "id" in m]

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        start = perf_counter()
        data = self._request("POST", "/chat/completions", {
            "model": self.model, "messages": messages, "tools": tools,
            "tool_choice": "auto", "max_tokens": 2048,
        })
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
                "seconds": perf_counter() - start, "model": data.get("model", self.model)}
