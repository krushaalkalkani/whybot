// Number formatters. Every formatter returns NOT_RUN for null, undefined or
// non-finite input, so tables never show a made-up number.

export const NOT_RUN = "not run yet";

type Num = number | null | undefined;

function ok(v: Num): v is number {
  return typeof v === "number" && Number.isFinite(v);
}

/** Fraction in [0, 1] -> "83.3%". */
export function fmtPercent(v: Num): string {
  return ok(v) ? `${(v * 100).toFixed(1)}%` : NOT_RUN;
}

/** Seconds -> "4.2 s". */
export function fmtSeconds(v: Num): string {
  return ok(v) ? `${v.toFixed(1)} s` : NOT_RUN;
}

/** USD -> "$0.0123". */
export function fmtUsd(v: Num): string {
  return ok(v) ? `$${v.toFixed(4)}` : NOT_RUN;
}

/** Plain decimal, default 1 digit -> "6.4". */
export function fmtDecimal(v: Num, digits = 1): string {
  return ok(v) ? v.toFixed(digits) : NOT_RUN;
}

/** Integer with thousands separators -> "12,345". */
export function fmtInt(v: Num): string {
  return ok(v) ? Math.round(v).toLocaleString("en-US") : NOT_RUN;
}

/** Text or NOT_RUN when missing or empty. */
export function fmtText(v: string | null | undefined): string {
  return typeof v === "string" && v.trim() !== "" ? v : NOT_RUN;
}

/** Milliseconds for the step trace -> "420 ms" or "3.2 s". */
export function fmtMs(v: Num): string {
  if (!ok(v)) return NOT_RUN;
  return v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`;
}

export type MetricKind = "percent" | "seconds" | "usd" | "count";

export function fmtMetric(kind: MetricKind, v: Num): string {
  switch (kind) {
    case "percent":
      return fmtPercent(v);
    case "seconds":
      return fmtSeconds(v);
    case "usd":
      return fmtUsd(v);
    case "count":
      return fmtDecimal(v, 1);
  }
}
