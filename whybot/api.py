"""FastAPI app.

  POST /ask         ask a question; the answer streams back as server-sent events
  GET  /runs/{id}   a stored run with all its steps
  GET  /limits      how many live questions this visitor has left today
  GET  /evals       the committed eval results (results/summary.json)
  GET  /health      liveness + database check

Logs are one JSON object per line.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from whybot import limits, store
from whybot.agent import AgentDeps, run_whybot
from whybot.config import REPO_ROOT, AgentConfig, Settings, get_settings
from whybot.db import connect
from whybot.llm import ClaudeLLM, LLMError
from whybot.retrieval.search import Retriever
from whybot.schemas import AskRequest, Report, RunRecord, Step
from whybot.tools import ToolContext

logger = logging.getLogger("whybot")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stdout))


def log(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"ts": datetime.now(UTC).isoformat(), "event": event, **fields}, default=str))


settings: Settings = get_settings()
app = FastAPI(
    title="WhyBot API", version="0.1.0", description="Cited root-cause analysis over a synthetic company."
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["*"]
)


@lru_cache(maxsize=1)
def shared_retriever() -> Retriever:
    """Loaded once per process: the BM25 index and the two ONNX models."""
    return Retriever(connect(settings.database_url), settings.models_dir)


@lru_cache(maxsize=1)
def shared_llm() -> ClaudeLLM:
    return ClaudeLLM(cache_dir=settings.llm_cache_dir)


def client_ip_hash(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return limits.hash_ip(ip, settings.ip_hash_salt)


def sse(event: str, data: Any) -> str:
    """One server-sent event frame."""
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def replay(record: RunRecord) -> Iterator[str]:
    """Stream a stored run. Costs nothing."""
    yield sse("run", {"run_id": record.id, "cached": True})
    for step in record.steps:
        yield sse("step", step.model_dump_json())
    if record.report:
        yield sse("report", record.report.model_dump_json())
    yield sse("done", {})


def live(question: str, run_id: str) -> Iterator[str]:
    """Run the agent and stream each step as it happens. Saves the run and its cost at the end."""
    started = time.time()
    conn = connect(settings.database_url)
    readonly = connect(settings.database_url_readonly)
    steps: list[Step] = []
    report: Report | None = None
    error: str | None = None
    yield sse("run", {"run_id": run_id, "cached": False})
    try:
        ctx = ToolContext(conn, readonly, shared_retriever().share(conn), AgentConfig().retrieval)
        deps = AgentDeps(shared_llm(), ctx, settings.agent_model, settings.agent_effort, AgentConfig())
        for event in run_whybot(question, deps):
            if isinstance(event, Report):
                report = event
                yield sse("report", event.model_dump_json())
            else:
                steps.append(event)
                yield sse("step", event.model_dump_json())
    except LLMError as exc:
        error = str(exc)
        yield sse(
            "error", {"code": "internal", "message": "The language model call failed. Please try again."}
        )
    except Exception as exc:  # never leak a stack trace to the browser
        error = f"{type(exc).__name__}: {exc}"
        yield sse("error", {"code": "internal", "message": "Something went wrong while investigating."})
    finally:
        cost = sum(s.cost_usd for s in steps)
        try:
            limits.add_spend(conn, cost)
            record = RunRecord(
                id=run_id, created_at=datetime.now(UTC).isoformat(), question=question, system="whybot",
                status="error" if error else "done", steps=steps, report=report, error=error,
            )  # fmt: skip
            store.save_run(conn, record)
        except psycopg.Error as exc:
            log("save_failed", run_id=run_id, error=str(exc))
        log("ask_done", run_id=run_id, status="error" if error else "done", steps=len(steps), cost_usd=round(cost, 6),
            latency_ms=int((time.time() - started) * 1000), verdict=report.verdict if report else None, error=error)  # fmt: skip
        conn.close()
        readonly.close()
    yield sse("done", {})


@app.post("/ask")
def ask(body: AskRequest, request: Request) -> StreamingResponse:
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    conn = connect(settings.database_url)
    try:
        cached = store.find_cached(conn, body.question)
        if cached:
            log("ask_cached", run_id=cached.id)
            return StreamingResponse(replay(cached), media_type="text/event-stream", headers=headers)
        ip_hash = client_ip_hash(request)
        state = limits.status(conn, settings, ip_hash)
        if not state.live_enabled:
            status_code = 503 if state.code == "no_llm" else 429
            raise HTTPException(status_code, {"code": state.code, "message": state.reason})
        limits.count_question(conn, ip_hash)
    finally:
        conn.close()
    return StreamingResponse(
        live(body.question, uuid.uuid4().hex[:16]), media_type="text/event-stream", headers=headers
    )


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> RunRecord:
    conn = connect(settings.database_url)
    try:
        record = store.get_run(conn, run_id)
    finally:
        conn.close()
    if record is None:
        raise HTTPException(404, {"code": "not_found", "message": "No run with this id."})
    return record


@app.get("/limits")
def get_limits(request: Request) -> dict[str, Any]:
    conn = connect(settings.database_url)
    try:
        state = limits.status(conn, settings, client_ip_hash(request))
    finally:
        conn.close()
    return {
        "live_enabled": state.live_enabled, "remaining_today": state.remaining_today,
        "daily_limit": state.daily_limit, "cap_reached": state.cap_reached, "reason": state.reason,
    }  # fmt: skip


@app.get("/evals")
def get_evals() -> dict[str, Any]:
    path = REPO_ROOT / "results" / "summary.json"
    if not path.exists():
        raise HTTPException(404, {"code": "not_found", "message": "No eval results yet."})
    return json.loads(path.read_text())


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        conn = connect(settings.database_url)
        row = conn.execute("SELECT count(*) AS n FROM documents").fetchone()
        documents = row["n"] if row else 0
        conn.close()
        return {
            "status": "ok",
            "documents": documents,
            "llm_configured": settings.has_llm_key,
            "agent_model": settings.agent_model,
        }
    except psycopg.Error as exc:
        raise HTTPException(503, {"code": "db_down", "message": str(exc).splitlines()[0]}) from exc
