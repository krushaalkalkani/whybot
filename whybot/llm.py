"""A thin wrapper around the Claude Messages API.

It adds three things the rest of the code relies on:
  - cost and latency for every call,
  - structured output: pass a Pydantic model, get a validated object back,
  - an on-disk cache keyed by a hash of the request, so evals can be replayed for free
    and give the same result every time.

Anything with a `complete` method of the same shape can stand in for it (see FakeLLM in tests).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

# USD per million tokens (input, output). Source: Anthropic pricing page, checked 2026-11-03.
# Haiku 5.5 costs more above 100K prompt tokens; WhyBot prompts stay far below that.
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


class CacheMiss(LLMError):
    """Raised in replay-only mode when a request is not in the cache."""


@dataclass
class LLMResult:
    content: list[dict[str, Any]]  # the assistant message blocks, as plain dicts
    stop_reason: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    cached: bool = False

    def text(self) -> str:
        return "".join(block["text"] for block in self.content if block["type"] == "text")

    def tool_uses(self) -> list[dict[str, Any]]:
        return [block for block in self.content if block["type"] == "tool_use"]

    def parse(self, model: type[T]) -> T:
        """Validate the JSON text against a Pydantic model."""
        return model.model_validate_json(self.text())


class LLM(Protocol):
    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        schema: type[BaseModel] | None = None,
        effort: str = "medium",
        max_tokens: int = 4000,
    ) -> LLMResult: ...


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, PRICES["claude-sonnet-5-5"])
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Turn a Pydantic model into the JSON schema shape structured outputs accept.

    Every object must list all its properties as required and forbid extra ones.
    """

    def fix(node: Any, is_property_map: bool = False) -> Any:
        if isinstance(node, dict):
            # Drop the schema keywords "title" and "default", but keep a property that is named "title".
            node = {
                k: fix(v, is_property_map=(k in ("properties", "$defs")))
                for k, v in node.items()
                if is_property_map or k not in ("title", "default")
            }
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
        elif isinstance(node, list):
            node = [fix(v) for v in node]
        return node

    return fix(model.model_json_schema())


def _clean_block(block: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields the API accepts when a block is sent back in the next request."""
    keep = {
        "text": ("type", "text"),
        "tool_use": ("type", "id", "name", "input"),
        "thinking": ("type", "thinking", "signature"),
        "redacted_thinking": ("type", "data"),
    }.get(block["type"])
    return {k: block[k] for k in keep if k in block} if keep else block


@dataclass
class ClaudeLLM:
    cache_dir: Path | None = None  # if set, results are stored in <cache_dir>/llm_cache.jsonl
    replay_only: bool = False  # if true, never call the API; raise CacheMiss instead
    _cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    _client: Any = None
    used_keys: set[str] = field(default_factory=set)  # cache entries read in this process
    _lock: threading.Lock = field(default_factory=threading.Lock)  # the eval runs scenarios in threads

    def __post_init__(self) -> None:
        if self.cache_dir and (self.cache_dir / "llm_cache.jsonl").exists():
            for line in open(self.cache_dir / "llm_cache.jsonl"):
                entry = json.loads(line)
                self._cache[entry["key"]] = entry["result"]

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        schema: type[BaseModel] | None = None,
        effort: str = "medium",
        max_tokens: int = 4000,
    ) -> LLMResult:
        request: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": effort},
        }
        if tools:
            request["tools"] = tools
        if schema is not None:
            request["output_config"]["format"] = {"type": "json_schema", "schema": strict_schema(schema)}

        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        if key in self._cache:
            self.used_keys.add(key)
            return LLMResult(**self._cache[key], cached=True)
        if self.replay_only:
            raise CacheMiss(f"LLM request {key[:12]} is not in the cache and replay_only is on.")

        import anthropic  # imported here so tests and replays need no API key

        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=4, timeout=120.0)
        started = time.time()
        try:
            response = self._client.messages.create(**request)
        except anthropic.APIError as error:
            raise LLMError(f"Claude API error: {error}") from error
        if response.stop_reason == "refusal":
            raise LLMError("The model declined this request.")
        usage = response.usage
        input_tokens = (
            usage.input_tokens
            + (usage.cache_read_input_tokens or 0)
            + (usage.cache_creation_input_tokens or 0)
        )
        result = {
            "content": [_clean_block(block.model_dump(mode="json")) for block in response.content],
            "stop_reason": response.stop_reason or "",
            "input_tokens": input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": cost_usd(model, input_tokens, usage.output_tokens),
            "latency_ms": int((time.time() - started) * 1000),
        }
        self._store(key, result)
        return LLMResult(**result)

    def _store(self, key: str, result: dict[str, Any]) -> None:
        with self._lock:
            self.used_keys.add(key)
            self._cache[key] = result
            if self.cache_dir:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                with open(self.cache_dir / "llm_cache.jsonl", "a") as f:
                    f.write(json.dumps({"key": key, "result": result}, sort_keys=True) + "\n")
