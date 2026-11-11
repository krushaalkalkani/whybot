import { ask, causeTypeLabels, sourceLabels } from "../../lib/content";
import { fmtInt, fmtMs, fmtUsd } from "../../lib/format";
import type { Cause, Confidence, EvidenceCard, Report, VerifiedClaim } from "../../lib/types";
import { Badge, Card, type Tone } from "../ui";
import { EvidenceChip, sourceTone } from "./EvidenceChip";

const confidenceTone: Record<Confidence, Tone> = { high: "ok", medium: "warn", low: "neutral" };

export function evidenceDomId(id: string): string {
  return `evidence-${id}`;
}

function VerifiedMark({ verified }: { verified: boolean | null }) {
  if (verified === true) return <Badge tone="ok">verified</Badge>;
  if (verified === false) return <Badge tone="bad">unverified</Badge>;
  return (
    <Badge tone="neutral" title="The verifier did not check this claim">
      unverified
    </Badge>
  );
}

function Claim({
  claim,
  evidence,
  onSelectEvidence,
}: {
  claim: VerifiedClaim;
  evidence: Record<string, EvidenceCard>;
  onSelectEvidence: (id: string) => void;
}) {
  return (
    <li className="border-t border-line py-2.5 first:border-t-0">
      <p className="text-sm leading-relaxed">{claim.text}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        <VerifiedMark verified={claim.verified} />
        {claim.evidence_ids.length === 0 ? (
          <span className="text-xs text-muted">no citations</span>
        ) : (
          claim.evidence_ids.map((id) => (
            <EvidenceChip key={id} id={id} card={evidence[id]} onSelect={onSelectEvidence} />
          ))
        )}
      </div>
      {claim.note ? <p className="mt-1 text-xs text-muted">Verifier: {claim.note}</p> : null}
    </li>
  );
}

function CauseCard({
  cause,
  evidence,
  onSelectEvidence,
}: {
  cause: Cause;
  evidence: Record<string, EvidenceCard>;
  onSelectEvidence: (id: string) => void;
}) {
  const segment =
    cause.segment_dimension === "all"
      ? "All segments"
      : `${cause.segment_dimension} = ${cause.segment_value}`;
  return (
    <Card className="p-4">
      <div className="flex items-start gap-3">
        <span
          aria-label={`Rank ${cause.rank}`}
          className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sunken font-mono text-sm font-semibold"
        >
          {cause.rank}
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="font-semibold leading-snug">{cause.title}</h4>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge tone="accent">{causeTypeLabels[cause.cause_type] ?? cause.cause_type}</Badge>
            <Badge mono>{segment}</Badge>
            <Badge tone={confidenceTone[cause.confidence] ?? "neutral"}>
              {cause.confidence} confidence
            </Badge>
          </div>
        </div>
      </div>
      <ul className="mt-3">
        {cause.claims.map((claim, i) => (
          <Claim key={i} claim={claim} evidence={evidence} onSelectEvidence={onSelectEvidence} />
        ))}
      </ul>
    </Card>
  );
}

function metaValue(v: unknown): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (Array.isArray(v) && v.every((x) => typeof x === "string" || typeof x === "number")) {
    return v.join(", ");
  }
  return JSON.stringify(v);
}

function EvidenceCardView({ card, flash }: { card: EvidenceCard; flash: boolean }) {
  const meta = Object.entries(card.meta ?? {});
  return (
    <Card
      id={evidenceDomId(card.id)}
      className={`scroll-mt-20 p-3.5 ${flash ? "flash-card" : ""}`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-mono text-sm font-semibold">{card.id}</span>
        <Badge tone={sourceTone(card.source)}>{sourceLabels[card.source] ?? card.source}</Badge>
        {card.quarantined ? (
          <Badge tone="bad" title={ask.quarantinedNote}>
            {ask.quarantinedBadge}
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-xs text-muted">{card.date}</span>
      </div>
      <h4 className="mt-2 text-sm font-medium leading-snug">{card.title}</h4>
      {card.quarantined ? <p className="mt-1 text-xs text-bad">{ask.quarantinedNote}</p> : null}
      <p
        className={`mt-2 whitespace-pre-wrap break-words text-sm leading-relaxed text-muted ${
          card.source === "metric" ? "overflow-x-auto rounded-md bg-sunken p-2.5 font-mono text-xs" : ""
        }`}
      >
        {card.body}
      </p>
      {meta.length > 0 || card.score !== null ? (
        <dl className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2.5 text-xs">
          {card.score !== null && card.score !== undefined ? (
            <div className="flex gap-1">
              <dt className="text-muted">score</dt>
              <dd className="font-mono">{card.score.toFixed(2)}</dd>
            </div>
          ) : null}
          {meta.map(([k, v]) => (
            <div key={k} className="flex min-w-0 gap-1">
              <dt className="text-muted">{k}</dt>
              <dd className="break-all font-mono">{metaValue(v)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </Card>
  );
}

function Total({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-3 py-2">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-mono text-sm font-medium">{value}</dd>
    </div>
  );
}

export function ReportView({
  report,
  flash,
  onSelectEvidence,
}: {
  report: Report;
  flash: { id: string; n: number } | null;
  onSelectEvidence: (id: string) => void;
}) {
  const answered = report.verdict === "answered";
  const evidence = report.evidence ?? {};
  const cards = Object.values(evidence);
  const causes = [...(report.causes ?? [])].sort((a, b) => a.rank - b.rank);
  const dropped = report.dropped_claims ?? [];
  const t = report.totals;

  return (
    <div className="space-y-6">
      <div
        role="status"
        className={`tone ${answered ? "tone-ok" : "tone-warn"} rounded-lg px-4 py-3`}
      >
        <div className="text-xs font-semibold uppercase tracking-wide">Verdict</div>
        <div className="text-lg font-semibold">
          {answered ? ask.verdictAnswered : ask.verdictInsufficient}
        </div>
        {!answered ? <p className="mt-1 text-sm">{ask.verdictInsufficientNote}</p> : null}
      </div>

      <p className="text-base leading-relaxed">{report.summary}</p>

      {t ? (
        <dl className="grid grid-cols-2 divide-line rounded-lg border border-line bg-surface sm:grid-cols-5 sm:divide-x">
          <Total label="Latency" value={fmtMs(t.latency_ms)} />
          <Total label="Tokens in / out" value={`${fmtInt(t.input_tokens)} / ${fmtInt(t.output_tokens)}`} />
          <Total label="Cost (USD)" value={fmtUsd(t.cost_usd)} />
          <Total label="Tool calls" value={fmtInt(t.tool_calls)} />
          <Total label="LLM calls" value={fmtInt(t.llm_calls)} />
        </dl>
      ) : null}

      {causes.length > 0 ? (
        <section aria-labelledby="causes-heading">
          <h3 id="causes-heading" className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
            {ask.causesHeading}
          </h3>
          <div className="space-y-3">
            {causes.map((cause) => (
              <CauseCard
                key={cause.rank}
                cause={cause}
                evidence={evidence}
                onSelectEvidence={onSelectEvidence}
              />
            ))}
          </div>
        </section>
      ) : null}

      {dropped.length > 0 ? (
        <details className="group rounded-lg border border-line bg-surface">
          <summary className="flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium">
            <svg
              aria-hidden="true"
              viewBox="0 0 12 12"
              className="h-3 w-3 transition-transform group-open:rotate-90"
            >
              <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
            </svg>
            {ask.droppedHeading} ({dropped.length})
          </summary>
          <div className="border-t border-line px-4 pb-2 pt-3">
            <p className="text-xs text-muted">{ask.droppedNote}</p>
            <ul className="mt-1">
              {dropped.map((claim, i) => (
                <Claim key={i} claim={claim} evidence={evidence} onSelectEvidence={onSelectEvidence} />
              ))}
            </ul>
          </div>
        </details>
      ) : null}

      {report.notes?.length ? (
        <section>
          <h3 className="mb-1.5 text-sm font-semibold uppercase tracking-wide text-muted">
            {ask.notesHeading}
          </h3>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted">
            {report.notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {cards.length > 0 ? (
        <section aria-labelledby="evidence-heading">
          <h3 id="evidence-heading" className="text-sm font-semibold uppercase tracking-wide text-muted">
            {ask.evidenceHeading} ({cards.length})
          </h3>
          <p className="mb-2 mt-0.5 text-xs text-muted">{ask.evidenceNote}</p>
          <div className="grid gap-3 md:grid-cols-2">
            {cards.map((card) => (
              <EvidenceCardView
                key={flash?.id === card.id ? `${card.id}-${flash.n}` : card.id}
                card={card}
                flash={flash?.id === card.id}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
