// The whole site is this one page: headline, the working demo, four numbers, six steps.
// Every number comes from src/data/summary.json. The hero picture is drawn from the real
// revenue series of the example case (src/data/case-s001.json). Nothing is typed by hand.

import type { Metadata } from "next";
import { Bricolage_Grotesque } from "next/font/google";
import { AskClient } from "../components/ask/AskClient";
import caseData from "../data/case-s001.json";
import { fmtPercent, fmtSeconds } from "../lib/format";
import { summary } from "../lib/summary";
import "./landing.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display" });

export const metadata: Metadata = {
  title: "WhyBot - find out why a metric moved",
};

type Sys = { system: string; metrics?: Record<string, number | null> | null };

function metric(system: string, key: string): number | null {
  const rows = (summary.splits?.test?.systems ?? []) as Sys[];
  return rows.find((r) => r.system === system)?.metrics?.[key] ?? null;
}

function PixelChart() {
  // The example case as pixels: one column per day of North America revenue, 28 days.
  // Column height is to scale. The day the payments failed is the bright column.
  const days = caseData.days;
  const ROWS = 16;
  const CELL = 20;
  const values = days.map((d) => d.revenue_na);
  const lo = Math.min(...values) * 0.72;
  const hi = Math.max(...values);
  const hit = days.findIndex((d) => d.date === caseData.incident_date);
  const cells: { x: number; y: number; tone: string }[] = [];
  days.forEach((d, col) => {
    const height = Math.max(1, Math.round(((d.revenue_na - lo) / (hi - lo)) * ROWS));
    for (let row = 0; row < height; row++) {
      const fromTop = height - 1 - row;
      // A fixed pattern (no randomness) thins out the top two rows, like a dither.
      const dither = (col * 7 + row * 13) % 5;
      if (fromTop === 0 && dither < 2) continue;
      const tone = col === hit ? "hit" : fromTop <= 1 ? "hi" : fromTop <= 4 ? "mid" : "lo";
      cells.push({ x: col * CELL, y: (ROWS - 1 - row) * CELL, tone });
    }
  });
  return (
    <svg
      viewBox={`0 0 ${days.length * CELL} ${ROWS * CELL + 46}`}
      className="cf-pixels"
      role="img"
      aria-label="Pixel chart of North America revenue over four weeks. One day, 19 February 2024, drops sharply and is highlighted."
    >
      {cells.map((c) => (
        <rect key={`${c.x}-${c.y}`} x={c.x + 1} y={c.y + 1} width={CELL - 2} height={CELL - 2} className={`cf-px-${c.tone}`} />
      ))}
      <line x1={hit * CELL + CELL / 2} x2={hit * CELL + CELL / 2} y1={ROWS * CELL + 4} y2={ROWS * CELL + 16} className="cf-px-tick" />
      <text x={hit * CELL + CELL / 2} y={ROWS * CELL + 36} textAnchor="middle" className="cf-px-label">
        {caseData.incident_date} / why?
      </text>
    </svg>
  );
}

const STEPS: [string, string][] = [
  ["Plan", "Read the question. Pick the metric and the day."],
  ["Triage", "Check the day is unusual for its weekday. Find which segment moved."],
  ["Investigate", "Search tickets, issues and deploys. Query the metrics."],
  ["Rank", "Write up to three causes. Every sentence cites its evidence."],
  ["Verify", "Check each sentence against what it cites. Drop the ones that fail."],
  ["Guard", "No solid proof? Answer \"not enough evidence\"."],
];

export default function HomePage() {
  const tests = summary.benchmark?.test;
  const stats: [string, string][] = [
    ["Right cause found", fmtPercent(metric("whybot", "accuracy_at_1"))],
    ["Citations correct", fmtPercent(metric("whybot", "citation_precision"))],
    ["Median time", fmtSeconds(metric("whybot", "latency_p50_s"))],
    ["Plain search, same test", fmtPercent(metric("rag", "accuracy_at_1"))],
  ];
  return (
    <div className={`cf-page ${display.variable}`}>
      <header className="cf-top">
        <span className="cf-brand">
          <i aria-hidden="true" />
          whybot
        </span>
        <span className="cf-tag">root-cause agent / synthetic data</span>
      </header>

      <main id="main">
        <section className="cf-hero">
          <div className="cf-hero-text">
            <h1>
              Why did the number move? <em>Ask. Get proof.</em>
            </h1>
            <p className="cf-lede">
              WhyBot checks the metrics, reads the tickets and the deploy log, and names the cause. Every sentence links to its
              evidence. When the evidence is weak, it says so.
            </p>
            <ul className="cf-bullets">
              <li>cites every claim</li>
              <li>abstains when unsure</li>
              <li>plain Python, no framework</li>
            </ul>
          </div>
          <PixelChart />
        </section>

        <section className="cf-demo" aria-label="Try WhyBot">
          <div className="cf-demo-head">
            <span>demo / pick an example or ask</span>
            <span className="cf-live">live</span>
          </div>
          <div className="cf-demo-body">
            <AskClient hideIntro />
          </div>
        </section>

        <section className="cf-block">
          <h2>
            Scored against <em>known answers</em>
          </h2>
          <dl className="cf-stats">
            {stats.map(([label, value], i) => (
              <div key={label} className={i === 3 ? "cf-dim" : undefined}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <p className="cf-caption">Measured once on {tests} held-out cases from a synthetic company with planted causes.</p>
        </section>

        <section className="cf-block cf-how">
          <h2>
            Six steps, <em>the same every time</em>
          </h2>
          <ol className="cf-steps">
            {STEPS.map(([name, text], i) => (
              <li key={name}>
                <span className="cf-num">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3>{name}</h3>
                  <p>{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="cf-footer">
        <p aria-hidden="true" className="cf-wordmark">
          whybot
        </p>
        <p className="cf-fine">Synthetic data. No real company or customer appears on this site.</p>
      </footer>
    </div>
  );
}
