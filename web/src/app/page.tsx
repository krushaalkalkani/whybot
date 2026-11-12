// The showcase page: a friendly "case file". One long page that tells the WhyBot story.
// Every number comes from src/data/summary.json or src/data/case-s001.json. None is typed by hand.
// All pictures are drawn here as SVG or built from real project data; there are no stock images.

import type { Metadata } from "next";
import { Caveat, Figtree, Fraunces } from "next/font/google";
import Link from "next/link";
import type { ReactNode } from "react";
import caseData from "../data/case-s001.json";
import example from "../data/examples/ex-S001.json";
import { fmtPercent, fmtSeconds, fmtUsd } from "../lib/format";
import { summary } from "../lib/summary";
import "./landing.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });
const body = Figtree({ subsets: ["latin"], variable: "--font-body" });
const hand = Caveat({ subsets: ["latin"], variable: "--font-hand" });

export const metadata: Metadata = {
  title: "WhyBot - a friendly AI investigator for business metrics, by Krushal Kalkani",
};

const LINKS = {
  github: "https://github.com/krushaalkalkani",
  repo: "https://github.com/krushaalkalkani/whybot",
  linkedin: "https://linkedin.com/in/krushal-kalkani",
  dataset: "https://huggingface.co/datasets/krushalkalkani/whybot-rca-bench",
  email: "krushalkalkani06@gmail.com",
};

type Sys = { system: string; metrics?: Record<string, number | null> | null };

function metric(system: string, key: string): number | null {
  const rows = (summary.splits?.test?.systems ?? []) as Sys[];
  return rows.find((r) => r.system === system)?.metrics?.[key] ?? null;
}

/* ------------------------------------------------------------------ pictures */

function Mascot({ className }: { className?: string }) {
  // "Why", the investigator: a round robot with a red cap and a magnifying glass.
  return (
    <svg viewBox="0 0 320 340" className={className} role="img" aria-label="WhyBot, a small robot detective holding a magnifying glass">
      <ellipse cx="160" cy="322" rx="92" ry="10" className="cf-i-shadow" />
      <line x1="160" y1="52" x2="160" y2="30" className="cf-i-stroke" />
      <circle cx="160" cy="24" r="9" className="cf-i-red" />
      <rect x="62" y="52" width="196" height="150" rx="58" className="cf-i-body" />
      <path d="M70 96 Q160 22 250 96 Z" className="cf-i-red" />
      <rect x="58" y="92" width="204" height="16" rx="8" className="cf-i-ink" />
      <rect x="88" y="118" width="144" height="62" rx="31" className="cf-i-face" />
      <circle cx="128" cy="148" r="11" className="cf-i-eye" />
      <circle cx="192" cy="148" r="11" className="cf-i-eye" />
      <circle cx="131" cy="145" r="3.5" className="cf-i-glint" />
      <circle cx="195" cy="145" r="3.5" className="cf-i-glint" />
      <path d="M146 164 Q160 174 174 164" className="cf-i-smile" />
      <rect x="92" y="210" width="136" height="96" rx="34" className="cf-i-body" />
      <rect x="126" y="232" width="68" height="40" rx="10" className="cf-i-face" />
      <polyline points="134,262 148,250 160,256 172,240 186,246" className="cf-i-spark" />
      <path d="M92 236 Q52 240 58 276" className="cf-i-arm" />
      <path d="M228 236 Q262 226 262 196" className="cf-i-arm" />
      <circle cx="268" cy="150" r="40" className="cf-i-lens" />
      <circle cx="268" cy="150" r="40" className="cf-i-ring" />
      <line x1="262" y1="192" x2="262" y2="200" className="cf-i-handle" />
      <text x="268" y="166" textAnchor="middle" className="cf-i-q">
        ?
      </text>
    </svg>
  );
}

const ICONS: Record<string, ReactNode> = {
  plan: <path d="M8 6h16M8 14h16M8 22h10M4 6h.01M4 14h.01M4 22h.01" />,
  triage: <path d="M4 24l7-9 5 5 8-12M22 8h4v4" />,
  investigate: (
    <>
      <circle cx="13" cy="13" r="8" />
      <path d="M19 19l7 7" />
    </>
  ),
  rank: <path d="M5 26V16h6v10M13 26V6h6v20M21 26V12h6v14" />,
  verify: <path d="M5 16l7 7L27 7" />,
  guard: <path d="M16 3l11 4v8c0 7-5 11-11 14C10 26 5 22 5 15V7z" />,
  loud: <path d="M4 12v8h5l9 6V6l-9 6zM23 11c2 3 2 7 0 10" />,
  weekend: (
    <>
      <rect x="4" y="6" width="24" height="22" rx="4" />
      <path d="M4 13h24M10 3v6M22 3v6M10 20h4M18 20h4" />
    </>
  ),
  unknown: (
    <>
      <circle cx="16" cy="16" r="12" />
      <path d="M12 12a4 4 0 117 3c-2 1-3 2-3 4M16 23h.01" />
    </>
  ),
  inject: <path d="M6 8h20v12H14l-6 6v-6H6zM11 14h10" />,
};

function Icon({ name, tone }: { name: string; tone: string }) {
  return (
    <span className={`cf-icon cf-tone-${tone}`} aria-hidden="true">
      <svg viewBox="0 0 32 32">{ICONS[name]}</svg>
    </span>
  );
}

function RevenueChart() {
  // North America revenue per day, drawn to scale. Weekends are shaded; the incident day is marked.
  const days = caseData.days;
  const W = 640;
  const H = 260;
  const left = 62;
  const right = 16;
  const top = 20;
  const bottom = 44;
  const values = days.map((d) => d.revenue_na);
  const lo = Math.floor(Math.min(...values) / 50000) * 50000;
  const hi = Math.ceil(Math.max(...values) / 50000) * 50000;
  const x = (i: number) => left + (i * (W - left - right)) / (days.length - 1);
  const y = (v: number) => top + ((hi - v) * (H - top - bottom)) / (hi - lo);
  const step = (W - left - right) / (days.length - 1);
  const hit = days.findIndex((d) => d.date === caseData.incident_date);
  const points = days.map((d, i) => `${x(i)},${y(d.revenue_na)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="cf-chart" role="img" aria-label="North America revenue per day, with a sharp drop on 19 February 2024">
      {days.map((d, i) => {
        const weekday = new Date(`${d.date}T00:00:00Z`).getUTCDay();
        return weekday === 0 || weekday === 6 ? (
          <rect key={d.date} x={x(i) - step / 2} y={top} width={step} height={H - top - bottom} rx={6} className="cf-weekend" />
        ) : null;
      })}
      {[lo, (lo + hi) / 2, hi].map((t) => (
        <g key={t}>
          <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} className="cf-grid" />
          <text x={left - 8} y={y(t) + 5} textAnchor="end" className="cf-tick">
            ${Math.round(t / 1000)}k
          </text>
        </g>
      ))}
      <polygon className="cf-area" points={`${x(0)},${y(lo)} ${points} ${x(days.length - 1)},${y(lo)}`} />
      <polyline fill="none" className="cf-line" points={points} />
      <circle cx={x(hit)} cy={y(days[hit].revenue_na)} r={13} className="cf-halo" />
      <circle cx={x(hit)} cy={y(days[hit].revenue_na)} r={6} className="cf-dot" />
      <text x={x(hit) - 16} y={y(days[hit].revenue_na) + 34} textAnchor="end" className="cf-callout">
        19 Feb: card payments fail
      </text>
      <text x={left} y={H - 12} className="cf-tick">
        {days[0].date}
      </text>
      <text x={W - right} y={H - 12} textAnchor="end" className="cf-tick">
        {days[days.length - 1].date}
      </text>
      <text x={(left + W - right) / 2} y={H - 12} textAnchor="middle" className="cf-tick">
        shaded = weekends
      </text>
    </svg>
  );
}

function DemoWindow() {
  // A picture of the real stored run: the same steps and answer the demo replays.
  const tools = example.steps.filter((s) => s.kind === "tool").slice(0, 4);
  const cause = example.report.causes[0];
  const totals = example.report.totals;
  return (
    <div className="cf-window" role="img" aria-label="The WhyBot demo showing its steps and the final answer for this case">
      <div className="cf-window-bar">
        <i />
        <i />
        <i />
        <span>whybot-ecru.vercel.app/demo</span>
      </div>
      <div className="cf-window-body">
        <div className="cf-ask">{caseData.question}</div>
        <ul className="cf-trace">
          {tools.map((s) => (
            <li key={s.index}>
              <b>{s.name.replaceAll("_", " ")}</b>
              <span>{s.latency_ms} ms</span>
            </li>
          ))}
          <li className="cf-trace-ok">
            <b>verify citations</b>
            <span>{cause.claims.length} of {cause.claims.length} supported</span>
          </li>
        </ul>
        <div className="cf-answer">
          <small>Top cause - {cause.confidence} confidence</small>
          <strong>{cause.title}</strong>
          <p>
            {cause.claims[0].evidence_ids.concat(cause.claims[3]?.evidence_ids ?? []).map((id) => (
              <code key={id}>{id}</code>
            ))}
            <span>
              {(totals.latency_ms / 1000).toFixed(1)} s - {fmtUsd(totals.cost_usd)}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ content */

const STEPS: [string, string, string, string][] = [
  ["plan", "sky", "Plan", "I read your question and pick the metric, the day and the segment."],
  ["triage", "mint", "Triage", "I check the day is unusual for its weekday, then find which region, platform or channel moved."],
  ["investigate", "sun", "Investigate", "I search tickets, issues and the deploy log, and run SQL on the metrics."],
  ["rank", "rose", "Rank", "I write up to three causes. Every sentence points to its evidence."],
  ["verify", "mint", "Verify", "I check each sentence against what it cites and remove the ones that fail."],
  ["guard", "sky", "Guard", "If no cause still stands on a real document, I say \"not enough evidence\"."],
];

const NOTES = [
  "The benchmark is too easy for the full system. Dev accuracy is at the ceiling, so I cannot show that the reranker or hybrid search helps end to end.",
  "Every system resisted all 8 prompt-injection cases, the baselines too. The model did that by itself. My defences are unit-tested, but the benchmark does not prove they were needed.",
  "The verifier checks claims, not the summary line. In this very case the summary misspells the provider's name. The claims under it are right.",
  "The data is synthetic and I wrote both the test and the system. Scores compare systems on this task. They do not predict accuracy at a real company.",
];

export default function CaseFilePage() {
  const report = example.report;
  const issue = report.evidence["ISS-0015"];
  const breakdown = report.evidence.M2;
  const b = summary.benchmark;
  const traps: [string, string, string, string][] = [
    ["loud", "sun", "Loud but unrelated", "A storm of complaints about something else on the same day."],
    ["weekend", "sky", "Normal weekend dips", "A real drop that is not an incident at all."],
    ["unknown", "mint", `${b?.unanswerable} with no answer`, "The number moved and nothing explains it. The right move is to say so."],
    ["inject", "rose", `${b?.injection} hijack attempts`, "Tickets with hidden instructions that try to steer the model."],
  ];
  const rows: [string, string][] = [
    ["llm_only", "The model alone"],
    ["rag", "Plain vector search + model"],
    ["whybot", "WhyBot"],
  ];
  return (
    <div className={`cf-page ${display.variable} ${body.variable} ${hand.variable}`}>
      <header className="cf-top">
        <Link href="/" className="cf-brand">
          <span aria-hidden="true">?</span> WhyBot
        </Link>
        <nav aria-label="Main" className="cf-nav">
          <Link href="/evals">Results</Link>
          <Link href="/how-it-works">How it works</Link>
          <a href={LINKS.repo} target="_blank" rel="noopener noreferrer">
            Code
          </a>
          <Link href="/demo" className="cf-nav-cta">
            Try the demo
          </Link>
        </nav>
      </header>

      <main id="main">
        <section className="cf-hero">
          <div className="cf-hero-text">
            <span className="cf-stamp">Case {caseData.scenario} - solved</span>
            <h1>
              Hi, I&apos;m WhyBot. <em>I find out why your numbers moved.</em>
            </h1>
            <p className="cf-lede">
              Ask me why a metric dropped. I check the data, read the tickets and the deploy log, and come back with the cause
              and the proof. If I am not sure, I tell you.
            </p>
            <div className="cf-actions">
              <Link href="/demo?run=ex-S001" className="cf-primary">
                Watch me solve a case
              </Link>
              <a href={LINKS.repo} target="_blank" rel="noopener noreferrer" className="cf-secondary">
                Read the code
              </a>
            </div>
            <p className="cf-byline">
              A project by <a href={LINKS.linkedin}>Krushal Kalkani</a>
            </p>
          </div>
          <div className="cf-hero-art">
            <Mascot className="cf-mascot" />
            <article className="cf-polaroid cf-p1">
              <b>Clue 1 - the numbers</b>
              {breakdown.body.split("\n")[0].replace("Overall revenue changed", "Revenue changed")}
            </article>
            <article className="cf-polaroid cf-p2">
              <b>Clue 2 - {issue.id}</b>
              {issue.title}
            </article>
            <span className="cf-scribble">solved in {(report.totals.latency_ms / 1000).toFixed(0)} seconds!</span>
          </div>
        </section>

        <section className="cf-stats">
          <div className="cf-stat cf-tone-sun">
            <strong>{fmtPercent(metric("whybot", "accuracy_at_1"))}</strong>
            <span>causes found on {b?.test} held-out cases</span>
          </div>
          <div className="cf-stat cf-tone-mint">
            <strong>{fmtPercent(metric("whybot", "citation_precision"))}</strong>
            <span>of cited documents were the right ones</span>
          </div>
          <div className="cf-stat cf-tone-sky">
            <strong>{fmtSeconds(metric("whybot", "latency_p50_s"))}</strong>
            <span>median time per investigation</span>
          </div>
          <div className="cf-stat cf-tone-rose">
            <strong>{fmtUsd(metric("whybot", "cost_per_query_usd"))}</strong>
            <span>model cost per investigation, at list prices</span>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">A real case</p>
          <h2>One bad Monday in North America</h2>
          <div className="cf-split">
            <figure className="cf-figure">
              <RevenueChart />
              <figcaption>North America revenue per day. Source: {caseData.source}.</figcaption>
            </figure>
            <div className="cf-prose">
              <p className="cf-quote">&ldquo;{caseData.question}&rdquo;</p>
              <p>
                Weekends always dip, so comparing with yesterday is useless. I compare each day with the same weekday in the six
                weeks before. On that basis 19 February is far out of range, and only one region moved.
              </p>
              <p>
                Then I searched the documents from those days and found an engineering issue about a payment provider rejecting
                good cards in that region. The numbers and the document agree, so I name the cause.
              </p>
            </div>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">See it work</p>
          <h2>Every answer shows its work</h2>
          <div className="cf-split cf-split-wide">
            <DemoWindow />
            <div className="cf-prose">
              <p>
                You see each step as it happens: which tool ran, how long it took, and what it found. The answer lists the
                evidence IDs behind every sentence, and you can click each one to read it.
              </p>
              <p>Six stored cases replay for free. You can also ask your own question.</p>
              <Link href="/demo" className="cf-primary">
                Open the demo
              </Link>
            </div>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">How I think</p>
          <h2>Six steps, the same every time</h2>
          <ol className="cf-steps">
            {STEPS.map(([icon, tone, name, text]) => (
              <li key={name}>
                <Icon name={icon} tone={tone} />
                <h3>{name}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
          <p className="cf-small">
            Under the hood: a plain Python state machine with no agent framework, FastAPI, Postgres with pgvector, hybrid search
            (BM25 + embeddings), Claude for the reasoning steps, an MCP server, and a CI gate that fails the build if accuracy
            drops.
          </p>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">The test</p>
          <h2>Scored against known answers</h2>
          <p className="cf-lede cf-narrow">
            I built a pretend company with {b?.scenarios} planted incidents, so every answer can be checked. Some cases are
            traps:
          </p>
          <div className="cf-traps">
            {traps.map(([icon, tone, title, text]) => (
              <div key={title} className="cf-trap">
                <Icon name={icon} tone={tone} />
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            ))}
          </div>
          <div className="cf-score">
            {rows.map(([id, label]) => {
              const value = metric(id, "accuracy_at_1");
              return (
                <div key={id} className={id === "whybot" ? "cf-bar-row cf-win" : "cf-bar-row"}>
                  <span>{label}</span>
                  <div className="cf-bar">
                    <i style={{ width: `${(value ?? 0) * 100}%` }} />
                  </div>
                  <strong>{fmtPercent(value)}</strong>
                </div>
              );
            })}
            <p className="cf-small">
              Share of the {b?.test} test cases where the right cause came first. The test cases were run once, after tuning on
              the other {b?.dev}. <Link href="/evals">All metrics and ablations</Link>
            </p>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">Honest notes</p>
          <h2>What did not hold up</h2>
          <ul className="cf-notes">
            {NOTES.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <section className="cf-section cf-author">
          <div className="cf-avatar" aria-hidden="true">
            KK
          </div>
          <div>
            <p className="cf-eyebrow">Built by</p>
            <h2>Krushal Kalkani</h2>
            <p className="cf-lede">
              MS in Computer Science, AI and machine learning. I am looking for AI engineer and ML engineer roles. Say hello.
            </p>
            <ul className="cf-links">
              <li>
                <a href={LINKS.linkedin} target="_blank" rel="noopener noreferrer">
                  LinkedIn
                </a>
              </li>
              <li>
                <a href={LINKS.github} target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
              </li>
              <li>
                <a href={`mailto:${LINKS.email}`}>{LINKS.email}</a>
              </li>
              <li>
                <a href={LINKS.dataset} target="_blank" rel="noopener noreferrer">
                  Benchmark dataset
                </a>
              </li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="cf-footer">Synthetic data. No real company or customer appears on this site.</footer>
    </div>
  );
}
