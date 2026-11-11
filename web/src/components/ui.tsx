import type { ReactNode } from "react";

export type Tone = "neutral" | "accent" | "ok" | "warn" | "bad" | "info" | "violet";

const toneClass: Record<Tone, string> = {
  neutral: "",
  accent: "tone-accent",
  ok: "tone-ok",
  warn: "tone-warn",
  bad: "tone-bad",
  info: "tone-info",
  violet: "tone-violet",
};

export function Badge({
  tone = "neutral",
  children,
  title,
  mono = false,
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  mono?: boolean;
}) {
  return (
    <span
      title={title}
      className={`tone ${toneClass[tone]} inline-flex items-center whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium leading-4 ${
        mono ? "font-mono" : ""
      }`}
    >
      {children}
    </span>
  );
}

export function Card({
  children,
  className = "",
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <div id={id} className={`rounded-lg border border-line bg-surface ${className}`}>
      {children}
    </div>
  );
}

export function SectionHeading({
  children,
  id,
  note,
}: {
  children: ReactNode;
  id?: string;
  note?: ReactNode;
}) {
  return (
    <div className="mb-3">
      <h2 id={id} className="scroll-mt-20 text-lg font-semibold tracking-tight">
        {children}
      </h2>
      {note ? <p className="mt-1 max-w-3xl text-sm text-muted">{note}</p> : null}
    </div>
  );
}

export function PageIntro({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-8 max-w-3xl">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      <p className="mt-3 text-base leading-relaxed text-muted">{children}</p>
    </div>
  );
}
