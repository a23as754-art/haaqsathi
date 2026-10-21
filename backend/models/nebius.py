"""Minimal Nebius Token Factory chat client (OpenAI-compatible endpoint).

Stdlib only for the Phase 1 smoke test. Model ID and base URL come from env and
must be verified against /v1/models for the account in use.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class ModelError(Exception):
    """Transport, HTTP, or output-validation failure (never includes secrets)."""


@dataclass
class ModelResult:
    content: str
    parsed: dict | None
    latency_s: float
    usage: dict


def extract_content(body: dict) -> str:
    """Reasoning models can return empty/null `content`; fail loudly instead of passing ''."""
    try:
        msg = body["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as e:
        raise ModelError("malformed response: no choices[0].message") from e
    content = msg.get("content")
    if not content or not str(content).strip():
        raise ModelError(
            "empty content (reasoning model may have spent max_tokens on reasoning; "
            "raise max_tokens or check finish_reason)"
        )
    return str(content)


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def parse_json_strict(text: str) -> dict:
    cleaned = _FENCE.sub("", text.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ModelError(f"output is not valid JSON: {e.msg}") from e
    if not isinstance(obj, dict):
        raise ModelError("output JSON is not an object")
    return obj


_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def validate_schema(obj: dict, schema: dict) -> None:
    """Tiny validator: required keys + top-level types. Replace with pydantic in the app."""
    for key in schema.get("required", []):
        if key not in obj:
            raise ModelError(f"missing required key: {key}")
    for key, spec in schema.get("properties", {}).items():
        if key in obj and "type" in spec:
            py = _TYPES.get(spec["type"])
            numeric = spec["type"] in ("integer", "number")
            if py and (not isinstance(obj[key], py) or (numeric and isinstance(obj[key], bool))):
                raise ModelError(f"key '{key}' has wrong type, expected {spec['type']}")


class NebiusClient:
    def __init__(self, api_key=None, base_url=None, model=None, timeout=60.0, retries=2, opener=None):
        self.api_key = api_key or os.environ.get("NEBIUS_API_KEY", "")
        self.base_url = (base_url or os.environ.get(
            "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")).rstrip("/") + "/"
        self.model = model or os.environ.get("NEBIUS_MODEL", "")
        self.timeout, self.retries = timeout, retries
        self._open = opener or urllib.request.urlopen
        if not self.api_key or not self.model:
            raise ModelError("NEBIUS_API_KEY and NEBIUS_MODEL must be set")

    def generate(self, messages, response_schema=None, max_tokens=2048, temperature=0.2) -> ModelResult:
        payload: dict = {"model": self.model, "messages": messages,
                         "max_tokens": max_tokens, "temperature": temperature}
        if response_schema:
            payload["response_format"] = {"type": "json_object"}
            # guided_json is documented for Nebius text generation; support for this
            # specific model is unverified until the smoke test runs.
            payload["guided_json"] = response_schema
        req = urllib.request.Request(
            self.base_url + "chat/completions", data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            t0 = time.monotonic()
            try:
                with self._open(req, timeout=self.timeout) as r:
                    body = json.loads(r.read().decode())
                content = extract_content(body)
                parsed = None
                if response_schema:
                    parsed = parse_json_strict(content)
                    validate_schema(parsed, response_schema)
                return ModelResult(content, parsed, time.monotonic() - t0, body.get("usage", {}))
            except urllib.error.HTTPError as e:
                last = ModelError(f"HTTP {e.code}")
                if e.code < 500 and e.code != 429:
                    raise last from None
            except (urllib.error.URLError, TimeoutError) as e:
                last = ModelError(f"transport error: {type(e).__name__}")
            time.sleep(min(2 ** attempt, 8))
        raise last or ModelError("unknown failure")
