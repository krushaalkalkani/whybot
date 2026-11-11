"""Test doubles. FakeLLM returns scripted answers so the agent loop runs with no API key."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from pydantic import BaseModel

from whybot.config import RetrievalConfig
from whybot.llm import LLMResult
from whybot.schemas import EvidenceCard


def text_reply(payload: BaseModel | dict[str, Any] | str) -> LLMResult:
    if isinstance(payload, BaseModel):
        text = payload.model_dump_json()
    elif isinstance(payload, dict):
        text = json.dumps(payload)
    else:
        text = payload
    return LLMResult([{"type": "text", "text": text}], "end_turn", 100, 50, 0.0001, 10)


def tool_reply(*calls: tuple[str, dict[str, Any]]) -> LLMResult:
    content = [
        {"type": "tool_use", "id": f"toolu_{i}", "name": n, "input": a} for i, (n, a) in enumerate(calls)
    ]
    return LLMResult(content, "tool_use", 100, 50, 0.0001, 10)


class FakeLLM:
    """Replies with the next scripted result. Records every request for assertions."""

    def __init__(self, replies: list[LLMResult]) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def complete(self, **request: Any) -> LLMResult:
        self.requests.append(request)
        if not self.replies:
            raise AssertionError("FakeLLM ran out of scripted replies")
        return self.replies.pop(0)


class FakeRetriever:
    """Returns fixed cards, so tests need no models and no vector search."""

    def __init__(self, cards: list[EvidenceCard]) -> None:
        self.cards = cards
        self.queries: list[str] = []

    def search(
        self,
        query: str,
        config: RetrievalConfig,
        date_from: date | None = None,
        date_to: date | None = None,
        source: str | None = None,
        k: int = 8,
    ) -> list[EvidenceCard]:
        self.queries.append(query)
        return [c.model_copy() for c in self.cards if source is None or c.source == source][:k]
