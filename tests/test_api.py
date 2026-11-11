"""API tests: health, stored runs, cached replay over server-sent events."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from whybot import api, store
from whybot.db import Conn
from whybot.schemas import Report, RunRecord, Step

pytestmark = pytest.mark.db


def test_health_and_limits(conn: Conn) -> None:
    client = TestClient(api.app)
    assert client.get("/health").json()["documents"] > 4000
    body = client.get("/limits").json()
    assert set(body) == {"live_enabled", "remaining_today", "daily_limit", "cap_reached", "reason"}


def test_stored_run_roundtrip_and_cached_replay(conn: Conn) -> None:
    report = Report(verdict="insufficient_evidence", summary="Not enough evidence.", causes=[], evidence={})
    step = Step(index=0, kind="plan", name="plan", title="Plan", cost_usd=0.001)
    record = RunRecord(id="test-run-1", created_at="2026-01-01T00:00:00+00:00", question="Why did test orders drop on 2024-05-05?",
                       system="whybot", status="done", steps=[step], report=report)  # fmt: skip
    store.save_run(conn, record, is_example=True)
    try:
        client = TestClient(api.app)
        assert client.get("/runs/test-run-1").json()["steps"][0]["title"] == "Plan"
        assert client.get("/runs/nope").status_code == 404
        # Same question, different case and spacing: served from the stored run, no LLM, no rate limit.
        response = client.post("/ask", json={"question": "why did  TEST orders drop on 2024-05-05"})
        events = [line.split(": ", 1)[1] for line in response.text.splitlines() if line.startswith("event: ")]
        assert events == ["run", "step", "report", "done"]
        first_data = next(line for line in response.text.splitlines() if line.startswith("data: "))
        assert json.loads(first_data[6:]) == {"run_id": "test-run-1", "cached": True}
    finally:
        conn.execute("DELETE FROM runs WHERE id = 'test-run-1'")
