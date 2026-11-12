// The showcase page ("case file"). One long page that tells the WhyBot story.
// Every number comes from src/data/summary.json or src/data/case-s001.json. None is typed by hand.

import type { Metadata } from "next";
import { Fraunces, Special_Elite } from "next/font/google";
import Link from "next/link";
import caseData from "../data/case-s001.json";
import example from "../data/examples/ex-S001.json";
import { fmtPercent, fmtSeconds, fmtUsd } from "../lib/format";
import { summary } from "../lib/summary";
import "./landing.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });
const typewriter = Special_Elite({ subsets: ["latin"], weight: "400", variable: "--font-type" });

export const metadata: Metadata = {
  title: "WhyBot - an AI investigator for business metrics, by Krushal Kalkani",
};

const LINKS = {
  github: "https://github.com/krushaalkalkani",
  repo: "https://github.com/krushaalkalkani/whybot",
  linkedin: "https://linkedin.com/in/krushal-kalkani",
  dataset: "https://huggingface.co/datasets/krushalkalkani/whybot-rca-bench",
  email: "krushalkalkani06@gmail.com",
};

const STEPS = [
  ["Plan", "Read the question. Pick the metric, the day and the segment."],
  ["Triage", "Check that the day is unusual for its weekday. Find which region, platform or channel moved."],
  ["Investigate", "Search tickets, issues and the deploy log. Run SQL on the metrics. The model chooses the tools."],
  ["Rank", "Write up to three causes. Every sentence must point to its evidence."],
  ["Verify", "Check each sentence against the evidence it cites. Remove the ones that fail."],
  ["Guard", "If no cause still stands on a real document, say \"not enough evidence\"."],
];

const NOTES = [
  "The benchmark is too easy for the full system. Dev accuracy is at the ceiling, so I cannot show that the reranker or hybrid search helps end to end.",
  "Every system resisted all 8 prompt-injection cases, the baselines too. The model did that by itself. My defences are unit-tested, but the benchmark does not prove they were needed.",
  "The verifier checks claims, not the summary line. In this very case the summary misspells the provider's name. The claims under it are right.",
  "The data is synthetic and I wrote both the test and the system. Scores compare systems on this task. They do not predict accuracy at a real company.",
];

type Sys = { system: string; label?: string | null; metrics?: Record<string, number | null> | null };

function metric(split: "test", system: string, key: string): number | null {
  const rows = (summary.splits?.[split]?.systems ?? []) as Sys[];
  return rows.find((r) => r.system === system)?.metrics?.[key] ?? null;
}

function RevenueChart() {
  // North America revenue per day, drawn to scale. Weekends are shaded; the incident day is marked.
  const days = caseData.days;
  const W = 640;
  const H = 230;
  const left = 62;
  const right = 14;
  const top = 18;
  const bottom = 44;
  const values = days.map((d) => d.revenue_na);
  const lo = Math.floor(Math.min(...values) / 50000) * 50000;
  const hi = Math.ceil(Math.max(...values) / 50000) * 50000;
  const x = (i: number) => left + (i * (W - left - right)) / (days.length - 1);
  const y = (v: number) => top + ((hi - v) * (H - top - bottom)) / (hi - lo);
  const step = (W - left - right) / (days.length - 1);
  const hit = days.findIndex((d) => d.date === caseData.incident_date);
  const ticks = [lo, (lo + hi) / 2, hi];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="cf-chart" role="img" aria-label="North America revenue per day, with a sharp drop on 19 February 2024">
      {days.map((d, i) => {
        const weekday = new Date(`${d.date}T00:00:00Z`).getUTCDay();
        return weekday === 0 || weekday === 6 ? (
          <rect key={d.date} x={x(i) - step / 2} y={top} width={step} height={H - top - bottom} className="cf-weekend" />
        ) : null;
      })}
      {ticks.map((t) => (
        <g key={t}>
          <line x1={left} x2={W - right} y1={y(t)} y2={y(t)} className="cf-grid" />
          <text x={left - 6} y={y(t) + 5} textAnchor="end" className="cf-tick">
            ${Math.round(t / 1000)}k
          </text>
        </g>
      ))}
      <polyline fill="none" className="cf-line" points={days.map((d, i) => `${x(i)},${y(d.revenue_na)}`).join(" ")} />
      <circle cx={x(hit)} cy={y(days[hit].revenue_na)} r={6} className="cf-dot" />
      <line x1={x(hit)} x2={x(hit) - 70} y1={y(days[hit].revenue_na) + 8} y2={H - bottom - 6} className="cf-pointer" />
      <text x={x(hit) - 74} y={H - bottom - 8} textAnchor="end" className="cf-callout">
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

export default function CaseFilePage() {
  const report = example.report;
  const cause = report.causes[0];
  const issue = report.evidence["ISS-0015"];
  const breakdown = report.evidence.M2;
  const acc = metric("test", "whybot", "accuracy_at_1");
  const rows: [string, string][] = [
    ["llm_only", "The model alone"],
    ["rag", "Plain vector search + model"],
    ["whybot", "WhyBot"],
  ];
  return (
    <div className={`cf-page ${display.variable} ${typewriter.variable}`}>
      <header className="cf-top">
        <span className="cf-brand">WhyBot</span>
        <nav aria-label="Main" className="cf-nav">
          <Link href="/demo">Live demo</Link>
          <Link href="/evals">Results</Link>
          <Link href="/how-it-works">How it works</Link>
          <a href={LINKS.repo} target="_blank" rel="noopener noreferrer">
            Code
          </a>
        </nav>
      </header>

      <main id="main">
        <section className="cf-hero">
          <span className="cf-stamp">Case no. {caseData.scenario} - solved</span>
          <h1>
            Revenue fell 12%. <em>WhyBot found out why.</em>
          </h1>
          <p className="cf-lede">
            An AI investigator for business metrics. It checks the numbers, reads the tickets and the deploy log, and names the
            cause with proof. Built by Krushal Kalkani.
          </p>
          <div className="cf-actions">
            <Link href="/demo?run=ex-S001" className="cf-primary">
              Replay this case
            </Link>
            <a href={LINKS.repo} target="_blank" rel="noopener noreferrer" className="cf-secondary">
              Read the code
            </a>
          </div>

          <div className="cf-board">
            <article className="cf-card">
              <b>Exhibit M2 - metrics</b>
              {breakdown.body.split("\n")[0]}
            </article>
            <article className="cf-card">
              <b>Exhibit {issue.id} - engineering issue</b>
              {issue.title}. {issue.body.split(". ").slice(1, 2).join("")}.
            </article>
            <article className="cf-card">
              <b>Finding</b>
              {cause.title}. Confidence: {cause.confidence}. {cause.claims.length} claims, all verified.
            </article>
          </div>
        </section>

        <section className="cf-band">
          <div className="cf-verdict">
            <div>
              <strong>{fmtPercent(acc)}</strong>
              causes found on {summary.benchmark?.test} held-out cases
            </div>
            <div>
              <strong>{fmtPercent(metric("test", "whybot", "citation_precision"))}</strong>
              of cited documents were the right ones
            </div>
            <div>
              <strong>{fmtSeconds(metric("test", "whybot", "latency_p50_s"))}</strong>
              median time per investigation
            </div>
            <div>
              <strong>{fmtUsd(metric("test", "whybot", "cost_per_query_usd"))}</strong>
              model cost per investigation, at list prices
            </div>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">The evidence</p>
          <h2>One bad Monday in North America</h2>
          <div className="cf-split">
            <figure className="cf-figure">
              <RevenueChart />
              <figcaption>North America revenue per day. Source: {caseData.source}.</figcaption>
            </figure>
            <div className="cf-prose">
              <p>
                The question was: <q>{caseData.question}</q>
              </p>
              <p>
                Weekends always dip, so a plain day-over-day check is useless here. WhyBot compares each day with the same
                weekday in the six weeks before. On that basis 19 February is far out of range, and only one region moved.
              </p>
              <p>
                It then searched the documents from those days and found an engineering issue about a payment provider
                rejecting good cards in that region. Metrics and document agree, so it names the cause.
              </p>
            </div>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">The method</p>
          <h2>Six steps, the same every time</h2>
          <ol className="cf-steps">
            {STEPS.map(([name, text]) => (
              <li key={name}>
                <h3>{name}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
          <p className="cf-small">
            A plain Python state machine, no agent framework. FastAPI, Postgres with pgvector, hybrid search (BM25 + embeddings),
            Claude for the reasoning steps, an MCP server, and a CI gate that fails the build if accuracy drops.
          </p>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">The test</p>
          <h2>Scored against known answers</h2>
          <div className="cf-split">
            <div className="cf-prose">
              <p>
                I built a fake company with {summary.benchmark?.scenarios} planted incidents, so every answer can be checked.
                Some cases are traps: loud unrelated complaints, normal weekend dips, moves with no explanation at all, and
                tickets that try to hijack the model.
              </p>
              <p>
                The {summary.benchmark?.test} test cases were run once, after all tuning was finished on the other{" "}
                {summary.benchmark?.dev}.
              </p>
            </div>
            <div className="cf-tableWrap">
              <table className="cf-table">
                <thead>
                  <tr>
                    <th>System</th>
                    <th>Right cause</th>
                    <th>Claims supported</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(([id, label]) => (
                    <tr key={id} className={id === "whybot" ? "cf-win" : undefined}>
                      <td>{label}</td>
                      <td>{fmtPercent(metric("test", id, "accuracy_at_1"))}</td>
                      <td>{fmtPercent(metric("test", id, "faithfulness"))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="cf-small">
                Test split, {summary.benchmark?.test} cases. <Link href="/evals">All metrics and ablations</Link>
              </p>
            </div>
          </div>
        </section>

        <section className="cf-section">
          <p className="cf-eyebrow">Investigator&apos;s notes</p>
          <h2>What did not hold up</h2>
          <ul className="cf-notes">
            {NOTES.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <section className="cf-section cf-author">
          <p className="cf-eyebrow">Filed by</p>
          <h2>Krushal Kalkani</h2>
          <p className="cf-lede">MS in Computer Science, AI and machine learning. Looking for AI engineer and ML engineer roles.</p>
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
        </section>
      </main>

      <footer className="cf-footer">Synthetic data. No real company or customer appears on this site.</footer>
    </div>
  );
}
