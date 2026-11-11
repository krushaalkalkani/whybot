import type { Tone } from "../ui";
import type { EvidenceCard } from "../../lib/types";

export function sourceTone(source: string): Tone {
  switch (source) {
    case "changelog":
      return "accent";
    case "issue":
      return "warn";
    case "ticket":
      return "violet";
    case "metric":
      return "info";
    default:
      return "neutral";
  }
}

/** Guess the source from the id prefix when the card is not loaded yet. */
export function sourceFromId(id: string): EvidenceCard["source"] | "unknown" {
  if (id.startsWith("CHG-")) return "changelog";
  if (id.startsWith("ISS-")) return "issue";
  if (id.startsWith("TKT-")) return "ticket";
  if (/^M\d+$/.test(id)) return "metric";
  return "unknown";
}

const toneClass: Record<Tone, string> = {
  neutral: "",
  accent: "tone-accent",
  ok: "tone-ok",
  warn: "tone-warn",
  bad: "tone-bad",
  info: "tone-info",
  violet: "tone-violet",
};

export function EvidenceChip({
  id,
  card,
  onSelect,
}: {
  id: string;
  card?: EvidenceCard;
  onSelect?: (id: string) => void;
}) {
  const tone = toneClass[sourceTone(card?.source ?? sourceFromId(id))];
  const base = `tone ${tone} inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-xs font-medium leading-4`;
  if (!card || !onSelect) {
    return (
      <span className={`${base} opacity-70`} title={card ? card.title : "Evidence card not in the report yet"}>
        {id}
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      title={`${card.title} - click to view`}
      className={`${base} cursor-pointer underline decoration-dotted underline-offset-2 hover:decoration-solid`}
    >
      {id}
      {card.quarantined ? <span aria-label="quarantined">(q)</span> : null}
    </button>
  );
}
