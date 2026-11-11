"""All data shapes used by WhyBot, in one place.

Every tool input, tool output, agent step and the final report is a Pydantic model.
That gives three things: validation of what the LLM sends, JSON schemas for the
Claude API, and one contract shared by the API, the eval harness and the web app.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

Metric = Literal[
    "sessions",
    "orders",
    "revenue",
    "conversion_rate",
    "payment_failure_rate",
    "avg_order_value",
]

Dimension = Literal["region", "platform", "channel"]
SegmentDimension = Literal["all", "region", "platform", "channel"]

DIMENSION_VALUES: dict[str, list[str]] = {
    "region": ["na", "eu", "uk", "apac", "latam"],
    "platform": ["web", "ios", "android"],
    "channel": ["organic", "paid_search", "email", "social"],
}

CauseType = Literal[
    "bad_deploy",
    "pricing_change",
    "regional_outage",
    "platform_bug",
    "campaign_end",
    "payment_provider_error",
    "seasonality",
]

# Shown to every system (LLM-only, RAG, WhyBot) so they all use the same labels.
CAUSE_DEFINITIONS: dict[str, str] = {
    "bad_deploy": "A release of one of our own services or frontends broke something.",
    "pricing_change": "A price, fee or shipping-threshold change made customers buy less.",
    "regional_outage": "Infrastructure in one region was down or degraded, so traffic was lost.",
    "platform_bug": (
        "A bug on one client platform (ios, android or web) that was NOT caused by our own deploy, "
        "for example an OS update or a third-party SDK."
    ),
    "campaign_end": "A marketing campaign ended or was paused, so one channel lost traffic.",
    "payment_provider_error": "An external payment provider failed or declined payments.",
    "seasonality": "A normal repeating pattern (for example the weekend dip). Not an incident.",
}

Confidence = Literal["high", "medium", "low"]
EvidenceSource = Literal["changelog", "issue", "ticket", "metric"]

# ---------------------------------------------------------------------------
# Tool inputs
# ---------------------------------------------------------------------------


class MetricQueryInput(BaseModel):
    """Input for run_metric_query."""

    sql: str = Field(description="One read-only SELECT statement over the daily_metrics table.")


class AnomalyInput(BaseModel):
    """Input for detect_anomaly."""

    metric: Metric
    date: str = Field(description="Day to test, as YYYY-MM-DD.")
    region: str | None = Field(default=None, description="Optional filter, e.g. 'eu'.")
    platform: str | None = Field(default=None, description="Optional filter, e.g. 'ios'.")
    channel: str | None = Field(default=None, description="Optional filter, e.g. 'email'.")


class DecomposeInput(BaseModel):
    """Input for decompose_by_segment."""

    metric: Metric
    date: str = Field(description="Day to explain, as YYYY-MM-DD.")


class SearchInput(BaseModel):
    """Input for search_evidence."""

    query: str = Field(description="What to look for, in plain words.")
    date_from: str | None = Field(default=None, description="Earliest document date, YYYY-MM-DD.")
    date_to: str | None = Field(default=None, description="Latest document date, YYYY-MM-DD.")
    source: Literal["changelog", "issue", "ticket"] | None = Field(
        default=None, description="Optional: only search one kind of document."
    )
    k: int = Field(default=8, description="How many documents to return (1-12).")


# ---------------------------------------------------------------------------
# Tool outputs
# ---------------------------------------------------------------------------


class MetricQueryOutput(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool


class AnomalyOutput(BaseModel):
    metric: str
    date: str
    filters: dict[str, str]
    value: float
    baseline: float  # median of the same weekday in the 6 weeks before
    pct_change: float  # (value - baseline) / baseline, in percent
    z_score: float  # robust z: distance from baseline in units of normal spread
    day_before_value: float
    pct_change_vs_day_before: float
    is_anomaly: bool  # |z| >= 3
    explanation: str


class SegmentChange(BaseModel):
    dimension: str
    value: str
    metric_value: float
    baseline: float
    pct_change: float
    z_score: float


class DecomposeOutput(BaseModel):
    metric: str
    date: str
    overall_pct_change: float
    segments: list[SegmentChange]
    concentrated_in: list[SegmentChange]  # slices that moved much more than their siblings
    explanation: str


class EvidenceCard(BaseModel):
    """One piece of evidence. The web app renders this as a card."""

    id: str  # CHG-0001, ISS-0001, TKT-00001, or M1, M2, ... for metric results
    source: EvidenceSource
    title: str
    date: str
    body: str
    meta: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    quarantined: bool = False  # true when the text looked like a prompt injection


class SearchOutput(BaseModel):
    query: str
    results: list[EvidenceCard]


# ---------------------------------------------------------------------------
# What the LLM writes (structured outputs)
# ---------------------------------------------------------------------------


class Plan(BaseModel):
    """Planner output: the question, parsed, plus a short plan."""

    metric: Metric
    date: str = Field(description="The day the user asks about, YYYY-MM-DD.")
    direction: Literal["drop", "rise"]
    region: str | None = Field(description="Set only if the question names a region, else null.")
    platform: str | None = Field(description="Set only if the question names a platform, else null.")
    channel: str | None = Field(description="Set only if the question names a channel, else null.")
    steps: list[str] = Field(description="3 to 5 short investigation steps.")


class Claim(BaseModel):
    text: str = Field(description="One factual sentence.")
    evidence_ids: list[str] = Field(description="IDs of the evidence that supports this sentence.")


class DraftCause(BaseModel):
    cause_type: CauseType
    segment_dimension: SegmentDimension = Field(
        description="Which dimension the cause is limited to, or 'all' if it hit everything."
    )
    segment_value: str = Field(description="The affected slice, e.g. 'eu' or 'ios'. Use 'all' if all.")
    title: str = Field(description="Short name of the cause, under 12 words.")
    confidence: Confidence
    claims: list[Claim] = Field(description="1 to 4 factual sentences, each with evidence IDs.")


class DraftReport(BaseModel):
    """Ranker output. Also used directly by the two baselines."""

    abstain: bool = Field(description="True if the evidence is too weak to name a cause.")
    abstain_reason: str = Field(description="Why, if abstain is true. Else an empty string.")
    summary: str = Field(description="Two or three sentences answering the question.")
    causes: list[DraftCause] = Field(description="Up to 3 causes, most likely first. Empty if abstain.")


class ClaimCheck(BaseModel):
    claim_number: int
    supported: bool
    reason: str = Field(description="One short sentence.")


class VerifierOutput(BaseModel):
    checks: list[ClaimCheck]


# ---------------------------------------------------------------------------
# Final report and run trace
# ---------------------------------------------------------------------------


class VerifiedClaim(BaseModel):
    text: str
    evidence_ids: list[str]
    verified: bool | None  # None when the verifier was switched off
    note: str = ""


class Cause(BaseModel):
    rank: int
    cause_type: CauseType
    segment_dimension: SegmentDimension
    segment_value: str
    title: str
    confidence: Confidence
    claims: list[VerifiedClaim]


class Totals(BaseModel):
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0


class Report(BaseModel):
    verdict: Literal["answered", "insufficient_evidence"]
    summary: str
    causes: list[Cause]
    evidence: dict[str, EvidenceCard]  # every evidence item cited by a kept claim
    dropped_claims: list[VerifiedClaim] = Field(default_factory=list)
    quarantined_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    totals: Totals = Field(default_factory=Totals)


StepKind = Literal["plan", "tool", "llm", "rank", "verify", "guard"]


class Step(BaseModel):
    """One step of the agent, as shown in the live trace and stored with the run."""

    index: int
    kind: StepKind
    name: str
    title: str  # short human text, e.g. "Search evidence: checkout errors"
    detail: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    is_error: bool = False
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class RunRecord(BaseModel):
    id: str
    created_at: str
    question: str
    system: str
    status: Literal["done", "error"]
    steps: list[Step]
    report: Report | None
    error: str | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=8, max_length=400)
