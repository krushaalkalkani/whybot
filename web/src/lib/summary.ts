// Typed view of src/data/summary.json. Everything can be null or missing.
// The evals page must render "not run yet" for any gap and never invent a number.

import summaryJson from "../data/summary.json";

type N = number | null | undefined;

export interface SystemRow {
  system: string;
  label?: string | null;
  group?: string | null;
  complete?: boolean | null;
  metrics?: Record<string, N> | null;
}

export interface SplitResult {
  run_date?: string | null;
  n?: N;
  systems?: SystemRow[] | null;
}

export interface RetrievalResult {
  split?: string | null;
  n_queries?: N;
  rows?: { config: string; recall_at_10?: N; mrr?: N }[] | null;
}

export interface JudgeCalibration {
  n?: N;
  agreement?: N;
  cohens_kappa?: N;
  judge_model?: string | null;
}

export interface SecurityResult {
  passed?: N;
  total?: N;
  tests?: { name: string; owasp?: string | null; passed?: boolean | null }[] | null;
}

export interface ErrorCategory {
  category: string;
  count?: N;
  example_ids?: string[] | null;
  fix?: string | null;
}

export interface Summary {
  generated_at?: string | null;
  benchmark?: Record<string, string | number | null | undefined> | null;
  models?: { agent?: string | null; judge?: string | null } | null;
  splits?: { dev?: SplitResult | null; test?: SplitResult | null } | null;
  retrieval?: RetrievalResult | null;
  judge_calibration?: JudgeCalibration | null;
  security?: SecurityResult | null;
  error_analysis?: ErrorCategory[] | null;
}

export const summary = summaryJson as unknown as Summary;

export function systemsInGroup(split: SplitResult | null | undefined, group: string): SystemRow[] {
  return (split?.systems ?? []).filter((s) => (s.group ?? "main") === group);
}
