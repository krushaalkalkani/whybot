import { ask, stepKindLabels } from "../../lib/content";
import { fmtInt, fmtMs, fmtUsd } from "../../lib/format";
import type { EvidenceCard, Step } from "../../lib/types";
import { Badge, type Tone } from "../ui";
import { EvidenceChip } from "./EvidenceChip";

const kindTone: Record<Step["kind"], Tone> = {
  plan: "accent",
  tool: "info",
  llm: "violet",
  rank: "warn",
  verify: "ok",
  guard: "neutral",
};

function Json({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <pre className="max-h-64 overflow-auto rounded-md bg-sunken p-2.5 font-mono text-xs leading-5">
        {JSON.stringify(value ?? {}, null, 2)}
      </pre>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-mono text-xs">{value}</dd>
    </div>
  );
}

function StepItem({
  step,
  evidence,
  onSelectEvidence,
}: {
  step: Step;
  evidence: Record<string, EvidenceCard> | null;
  onSelectEvidence: (id: string) => void;
}) {
  return (
    <li className="step-in relative pl-6">
      <span
        aria-hidden="true"
        className={`absolute left-0 top-3.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full border-2 border-bg ${
          step.is_error ? "bg-bad" : "bg-accent"
        }`}
      />
      <details className="group rounded-lg border border-line bg-surface">
        <summary className="rounded-lg px-3 py-2.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Badge tone={kindTone[step.kind] ?? "neutral"}>
              {stepKindLabels[step.kind] ?? step.kind}
            </Badge>
            <span className="text-sm font-medium">{step.title}</span>
            {step.is_error ? <Badge tone="bad">Error</Badge> : null}
            <span className="ml-auto flex items-center gap-1.5 font-mono text-xs text-muted">
              {fmtMs(step.latency_ms)}
              <svg
                aria-hidden="true"
                viewBox="0 0 12 12"
                className="h-3 w-3 transition-transform group-open:rotate-90"
              >
                <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
              </svg>
            </span>
          </div>
          {step.detail ? <p className="mt-1 text-sm text-muted">{step.detail}</p> : null}
        </summary>
        <div className="space-y-3 border-t border-line px-3 py-3">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
            <Stat label="Name" value={step.name} />
            <Stat label="Latency" value={fmtMs(step.latency_ms)} />
            <Stat
              label="Tokens in / out"
              value={`${fmtInt(step.input_tokens)} / ${fmtInt(step.output_tokens)}`}
            />
            <Stat label="Cost" value={fmtUsd(step.cost_usd)} />
          </dl>
          {step.evidence_ids?.length ? (
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-muted">Evidence</span>
              {step.evidence_ids.map((id) => (
                <EvidenceChip
                  key={id}
                  id={id}
                  card={evidence?.[id]}
                  onSelect={onSelectEvidence}
                />
              ))}
            </div>
          ) : null}
          <Json label="Input" value={step.input} />
          <Json label="Output" value={step.output} />
        </div>
      </details>
    </li>
  );
}

export function StepTrace({
  steps,
  running,
  evidence,
  onSelectEvidence,
}: {
  steps: Step[];
  running: boolean;
  evidence: Record<string, EvidenceCard> | null;
  onSelectEvidence: (id: string) => void;
}) {
  if (steps.length === 0 && !running) {
    return (
      <p className="rounded-lg border border-dashed border-line px-4 py-6 text-sm text-muted">
        {ask.traceEmpty}
      </p>
    );
  }
  return (
    <ol className="ml-1.5 space-y-2 border-l border-line" aria-live="polite">
      {steps.map((step) => (
        <StepItem
          key={step.index}
          step={step}
          evidence={evidence}
          onSelectEvidence={onSelectEvidence}
        />
      ))}
      {running ? (
        <li className="relative pl-6">
          <span
            aria-hidden="true"
            className="pulse-dot absolute left-0 top-1.5 h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-accent"
          />
          <span className="text-sm text-muted">
            {steps.length === 0 ? "Starting..." : "Working on the next step..."}
          </span>
        </li>
      ) : null}
    </ol>
  );
}
