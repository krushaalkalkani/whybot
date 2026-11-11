"""Save and load runs (the question, every step, the report) in Postgres."""

from __future__ import annotations

import json
import re

from whybot.db import Conn
from whybot.schemas import Report, RunRecord, Step


def question_key(question: str) -> str:
    """Normalise a question so trivially different spellings hit the same cached run."""
    return re.sub(r"\s+", " ", question.strip().lower()).rstrip("?.! ")


def save_run(conn: Conn, record: RunRecord, is_example: bool = False) -> None:
    totals = record.report.totals if record.report else None
    with conn.transaction():
        conn.execute("DELETE FROM runs WHERE id = %s", (record.id,))
        conn.execute(
            """INSERT INTO runs (id, question, question_key, system, status, report, error, is_example,
                                 latency_ms, input_tokens, output_tokens, cost_usd)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                record.id,
                record.question,
                question_key(record.question),
                record.system,
                record.status,
                record.report.model_dump_json() if record.report else None,
                record.error,
                is_example,
                totals.latency_ms if totals else 0,
                totals.input_tokens if totals else 0,
                totals.output_tokens if totals else 0,
                sum(s.cost_usd for s in record.steps),
            ),  # fmt: skip
        )
        for step in record.steps:
            conn.execute(
                "INSERT INTO tool_traces (run_id, step_index, step) VALUES (%s, %s, %s)",
                (record.id, step.index, step.model_dump_json()),
            )


def _load(conn: Conn, row: dict) -> RunRecord:
    steps = conn.execute(
        "SELECT step FROM tool_traces WHERE run_id = %s ORDER BY step_index", (row["id"],)
    ).fetchall()
    return RunRecord(
        id=row["id"], created_at=row["created_at"].isoformat(), question=row["question"], system=row["system"],
        status=row["status"], steps=[Step.model_validate(s["step"]) for s in steps],
        report=Report.model_validate(row["report"]) if row["report"] else None, error=row["error"],
    )  # fmt: skip


def get_run(conn: Conn, run_id: str) -> RunRecord | None:
    row = conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()
    return _load(conn, row) if row else None


def find_cached(conn: Conn, question: str) -> RunRecord | None:
    """A finished run for the same question, if any. Examples first, then the newest."""
    row = conn.execute(
        "SELECT * FROM runs WHERE question_key = %s AND status = 'done' ORDER BY is_example DESC, created_at DESC LIMIT 1",
        (question_key(question),),
    ).fetchone()
    return _load(conn, row) if row else None


def to_json(obj: object) -> str:
    return json.dumps(obj, default=str)
