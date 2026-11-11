// Mirrors the backend contract. Keep in sync with the FastAPI models.

export type CauseType =
  | "bad_deploy"
  | "pricing_change"
  | "regional_outage"
  | "platform_bug"
  | "campaign_end"
  | "payment_provider_error"
  | "seasonality";

export type Confidence = "high" | "medium" | "low";

export interface EvidenceCard {
  id: string;
  source: "changelog" | "issue" | "ticket" | "metric";
  title: string;
  date: string;
  body: string;
  meta: Record<string, unknown>;
  score: number | null;
  quarantined: boolean;
}

export interface VerifiedClaim {
  text: string;
  evidence_ids: string[];
  verified: boolean | null;
  note: string;
}

export interface Cause {
  rank: number;
  cause_type: CauseType;
  segment_dimension: "all" | "region" | "platform" | "channel";
  segment_value: string;
  title: string;
  confidence: Confidence;
  claims: VerifiedClaim[];
}

export interface Totals {
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  llm_calls: number;
  tool_calls: number;
}

export interface Report {
  verdict: "answered" | "insufficient_evidence";
  summary: string;
  causes: Cause[];
  evidence: Record<string, EvidenceCard>;
  dropped_claims: VerifiedClaim[];
  quarantined_ids: string[];
  notes: string[];
  totals: Totals;
}

export interface Step {
  index: number;
  kind: "plan" | "tool" | "llm" | "rank" | "verify" | "guard";
  name: string;
  title: string;
  detail: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  evidence_ids: string[];
  is_error: boolean;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface RunRecord {
  id: string;
  created_at: string;
  question: string;
  system: string;
  status: "done" | "error";
  steps: Step[];
  report: Report | null;
  error: string | null;
}

// API-only shapes

export interface Limits {
  live_enabled: boolean;
  remaining_today: number;
  daily_limit: number;
  cap_reached: boolean;
  reason: string | null;
}

export type ApiErrorCode =
  | "rate_limited"
  | "spend_cap"
  | "no_llm"
  | "bad_request"
  | "timeout"
  | "internal";

export interface ApiError {
  code: ApiErrorCode;
  message: string;
}

export interface RunEvent {
  run_id: string;
  cached: boolean;
}

export interface ExampleIndexEntry {
  id: string;
  question: string;
  tag: string;
}
