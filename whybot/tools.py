"""The four tools the agent can call.

  run_metric_query      read-only SQL over daily_metrics
  detect_anomaly        is this day unusual for this metric?
  decompose_by_segment  which region / platform / channel moved?
  search_evidence       hybrid search over tickets, issues and the changelog

Each tool is a plain function: Pydantic input in, Pydantic output out.
`TOOLS` at the bottom is the registry the agent, the API and the MCP server share.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from whybot.config import RetrievalConfig
from whybot.db import Conn
from whybot.retrieval.search import Retriever
from whybot.schemas import (
    DIMENSION_VALUES,
    AnomalyInput,
    AnomalyOutput,
    DecomposeInput,
    DecomposeOutput,
    MetricQueryInput,
    MetricQueryOutput,
    SearchInput,
    SearchOutput,
    SegmentChange,
)
from whybot.sql_guard import ALLOWED_COLUMNS, MAX_ROWS, check_sql

# How each metric is computed from the raw columns.
METRIC_SQL: dict[str, str] = {
    "sessions": "SUM(sessions)::float",
    "orders": "SUM(orders)::float",
    "revenue": "SUM(revenue)::float",
    "conversion_rate": "SUM(orders)::float / NULLIF(SUM(sessions), 0)",
    "payment_failure_rate": "SUM(payment_failures)::float / NULLIF(SUM(payment_attempts), 0)",
    "avg_order_value": "SUM(revenue)::float / NULLIF(SUM(orders), 0)",
}
BASELINE_WEEKS = 6
Z_THRESHOLD = 3.0


class ToolError(Exception):
    """A problem the model can fix (bad date, rejected SQL). Its text is sent back to the model."""


@dataclass
class ToolContext:
    """What tools need to do their job."""

    conn: Conn  # normal connection (documents, chunks)
    readonly_conn: Conn  # restricted connection for LLM-written SQL
    retriever: Retriever
    retrieval: RetrievalConfig


# --------------------------------------------------------------------------- shared maths


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise ToolError(f"'{text}' is not a date. Use YYYY-MM-DD.") from error


def robust_z(value: float, history: list[float]) -> tuple[float, float]:
    """Compare `value` with past values. Returns (baseline, z).

    Baseline = median. Spread = median absolute deviation (MAD), scaled to match a
    standard deviation. Median and MAD ignore a few odd past days (for example an
    earlier incident), which mean and standard deviation do not.
    The spread has a floor of 1% of the baseline so tiny noise cannot give a huge z.
    """
    baseline = statistics.median(history)
    mad = statistics.median(abs(x - baseline) for x in history)
    spread = max(1.4826 * mad, 0.01 * abs(baseline), 1e-9)
    return baseline, (value - baseline) / spread


def pct(value: float, baseline: float) -> float:
    return 0.0 if baseline == 0 else (value - baseline) / baseline * 100.0


def daily_values(
    conn: Conn, metric: str, days: list[date], group_by: str | None, filters: dict[str, str]
) -> dict[tuple[str, date], float]:
    """Metric value per (segment value, day). Segment value is 'all' when group_by is None."""
    where = ["date = ANY(%(days)s)"]
    params: dict[str, Any] = {"days": days}
    for column, value in filters.items():
        where.append(f"{column} = %({column})s")  # column names come from our own code, never the model
        params[column] = value
    segment = group_by if group_by else "'all'"
    sql = f"SELECT {segment} AS segment, date, {METRIC_SQL[metric]} AS value FROM daily_metrics WHERE {' AND '.join(where)} GROUP BY 1, 2"
    rows = conn.execute(sql, params).fetchall()
    return {(r["segment"], r["date"]): float(r["value"] or 0.0) for r in rows}


def comparison_days(day: date) -> list[date]:
    """The day itself, the day before, and the same weekday in each of the 6 weeks before."""
    return [day, day - timedelta(days=1)] + [day - timedelta(weeks=w) for w in range(1, BASELINE_WEEKS + 1)]


# --------------------------------------------------------------------------- the tools


def run_metric_query(args: MetricQueryInput, ctx: ToolContext) -> MetricQueryOutput:
    safe_sql = check_sql(args.sql)  # raises SqlRejected (a ValueError) with a model-readable message
    with ctx.readonly_conn.transaction():
        ctx.readonly_conn.execute("SET TRANSACTION READ ONLY")
        ctx.readonly_conn.execute("SET LOCAL statement_timeout = '3s'")
        cursor = ctx.readonly_conn.execute(safe_sql)
        columns = [c.name for c in cursor.description or []]
        raw = cursor.fetchall()

    def clean(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, date):
            return str(value)
        return value

    rows = [[clean(r[c]) for c in columns] for r in raw]
    return MetricQueryOutput(
        columns=columns,
        rows=rows[:MAX_ROWS],
        row_count=min(len(rows), MAX_ROWS),
        truncated=len(rows) > MAX_ROWS,
    )


def detect_anomaly(args: AnomalyInput, ctx: ToolContext) -> AnomalyOutput:
    day = parse_day(args.date)
    filters: dict[str, str] = {}
    for column in ("region", "platform", "channel"):
        value = getattr(args, column)
        if value:
            if value not in DIMENSION_VALUES[column]:
                raise ToolError(f"Unknown {column} '{value}'. Valid: {DIMENSION_VALUES[column]}")
            filters[column] = value
    values = daily_values(ctx.conn, args.metric, comparison_days(day), None, filters)
    if ("all", day) not in values:
        raise ToolError(f"No data for {day}. Data covers 2024-01-01 to 2025-12-31.")
    history = [values[("all", d)] for d in comparison_days(day)[2:] if ("all", d) in values]
    if len(history) < 3:
        raise ToolError(f"Not enough history before {day} to judge it.")
    value = values[("all", day)]
    baseline, z = robust_z(value, history)
    before = values.get(("all", day - timedelta(days=1)), value)
    change, change_before = pct(value, baseline), pct(value, before)
    is_anomaly = abs(z) >= Z_THRESHOLD
    where = " for " + ", ".join(f"{k}={v}" for k, v in filters.items()) if filters else ""
    verdict = (
        f"This is unusual (|z| >= {Z_THRESHOLD:.0f})."
        if is_anomaly
        else "This is within the normal range for this weekday, so it is not an anomaly."
    )
    explanation = (
        f"{args.metric}{where} on {day} ({day.strftime('%A')}) was {value:.4g}. "
        f"The same weekday in the {len(history)} weeks before had a median of {baseline:.4g}. "
        f"Change vs that baseline: {change:+.1f}% (z = {z:+.1f}). "
        f"Change vs the day before: {change_before:+.1f}%. {verdict}"
    )
    return AnomalyOutput(
        metric=args.metric, date=str(day), filters=filters, value=round(value, 6), baseline=round(baseline, 6),
        pct_change=round(change, 2), z_score=round(z, 2), day_before_value=round(before, 6),
        pct_change_vs_day_before=round(change_before, 2), is_anomaly=is_anomaly, explanation=explanation,
    )  # fmt: skip


def decompose_by_segment(args: DecomposeInput, ctx: ToolContext) -> DecomposeOutput:
    """For each dimension, compare every slice with its own baseline.

    If one slice moved much more than its siblings, the change is concentrated there.
    If all slices of a dimension moved about the same, that dimension does not explain it.
    """
    day = parse_day(args.date)
    days = comparison_days(day)
    overall = daily_values(ctx.conn, args.metric, days, None, {})
    if ("all", day) not in overall:
        raise ToolError(f"No data for {day}. Data covers 2024-01-01 to 2025-12-31.")
    overall_baseline, _ = robust_z(
        overall[("all", day)], [overall[("all", d)] for d in days[2:] if ("all", d) in overall]
    )
    overall_change = pct(overall[("all", day)], overall_baseline)

    segments: list[SegmentChange] = []
    concentrated: list[SegmentChange] = []
    for dimension, names in DIMENSION_VALUES.items():
        values = daily_values(ctx.conn, args.metric, days, dimension, {})
        rows = []
        for name in names:
            history = [values[(name, d)] for d in days[2:] if (name, d) in values]
            if (name, day) not in values or len(history) < 3:
                continue
            baseline, z = robust_z(values[(name, day)], history)
            rows.append(
                SegmentChange(
                    dimension=dimension,
                    value=name,
                    metric_value=round(values[(name, day)], 6),
                    baseline=round(baseline, 6),
                    pct_change=round(pct(values[(name, day)], baseline), 2),
                    z_score=round(z, 2),
                )  # fmt: skip
            )
        segments += rows
        for row in rows:
            siblings = [r.pct_change for r in rows if r.value != row.value]
            gap = abs(row.pct_change - statistics.median(siblings)) if siblings else 0.0
            if gap >= 8.0 and abs(row.z_score) >= Z_THRESHOLD:  # moved 8+ points more than its siblings
                concentrated.append(row)

    if concentrated:
        parts = [f"{s.dimension}={s.value} ({s.pct_change:+.1f}%)" for s in concentrated]
        explanation = f"Overall {args.metric} changed {overall_change:+.1f}% on {day}. The change is concentrated in: {', '.join(parts)}. Other slices moved much less."
    else:
        explanation = f"Overall {args.metric} changed {overall_change:+.1f}% on {day}. No single region, platform or channel stands out; the slices moved about the same."
    return DecomposeOutput(
        metric=args.metric, date=str(day), overall_pct_change=round(overall_change, 2),
        segments=segments, concentrated_in=concentrated, explanation=explanation,
    )  # fmt: skip


def search_evidence(args: SearchInput, ctx: ToolContext) -> SearchOutput:
    date_from = parse_day(args.date_from) if args.date_from else None
    date_to = parse_day(args.date_to) if args.date_to else None
    k = max(1, min(args.k, 12))
    cards = ctx.retriever.search(args.query, ctx.retrieval, date_from, date_to, args.source, k)
    return SearchOutput(query=args.query, results=cards)


# --------------------------------------------------------------------------- registry


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[Any, ToolContext], BaseModel]

    def claude_spec(self) -> dict[str, Any]:
        """The tool definition in the shape the Claude API expects."""
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        schema.pop("description", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool(
            "run_metric_query",
            "Run one read-only SQL SELECT on the table daily_metrics (PostgreSQL). "
            f"Columns: {ALLOWED_COLUMNS}. One row per date x region x platform x channel. "
            "Rates are not stored: compute them, e.g. conversion_rate = SUM(orders)::float / SUM(sessions), "
            "payment_failure_rate = SUM(payment_failures)::float / SUM(payment_attempts). "
            "Use it to look at trends over several days or at a combination of segments. Returns at most 200 rows.",
            MetricQueryInput,
            run_metric_query,
        ),
        Tool(
            "detect_anomaly",
            "Check if a metric was unusual on one day. Compares the day with the same weekday in the 6 weeks "
            "before (robust z-score), so normal weekly patterns such as the weekend dip are not flagged. "
            "Optional filters: region, platform, channel.",
            AnomalyInput,
            detect_anomaly,
        ),
        Tool(
            "decompose_by_segment",
            "Find which region, platform or channel drove a metric change on one day. Each slice is compared "
            "with its own weekday baseline. Tells you if the change is concentrated in one slice.",
            DecomposeInput,
            decompose_by_segment,
        ),
        Tool(
            "search_evidence",
            "Search support tickets, GitHub issues and the deploy changelog. Hybrid keyword + semantic search. "
            "Always pass date_from and date_to to stay near the day in question. Use `source` to search one kind only "
            "(changelog = deploys and config changes, issue = engineering reports, ticket = customer messages).",
            SearchInput,
            search_evidence,
        ),
    ]
}
