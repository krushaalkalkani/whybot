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

const REPO = "https://github.com/krushaalkalkani/whybot";

function GitHubMark() {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  );
}

// The system as a small diagram. Boxes are the real modules; labels are the real tool names.
function Architecture() {
  return (
    <figure className="cf-arch">
      <figcaption>
        <span>architecture / one request</span>
        <span className="cf-live">whybot/agent.py</span>
      </figcaption>
      <pre>{`question
   |
   v
[ plan ] --> [ triage ]          detect_anomaly
                 |               decompose_by_segment
                 v
          [ investigate ] <----> search_evidence
                 |               run_metric_query
                 v
[ rank ] --> [ verify ] --> [ guard ]
                                |
                                v
                 answer + evidence, or
                 "not enough evidence"`}</pre>
      <p>$ postgres + pgvector / bm25 + embeddings / claude</p>
    </figure>
  );
}

const FAQS: [string, string][] = [
  [
    "Is the data real?",
    "No. I built a pretend online shop with two years of metrics, tickets, issues and deploys, and planted 80 incidents in it. Because I planted them, every answer can be checked.",
  ],
  [
    "How do you know an answer is right?",
    "Each test question has a known cause and known evidence. An answer counts only if the cause type and the affected segment both match. The 40 test cases were run once, after tuning on the other 40.",
  ],
  [
    "What happens when there is no evidence?",
    "WhyBot says \"not enough evidence\". A cause is kept only if a real document supports it and that claim passes a separate verification step.",
  ],
  [
    "What are the limits?",
    "The benchmark is synthetic and turned out easy for the full system, so it cannot show which parts matter most. Scores compare systems on this task. They do not predict accuracy at a real company.",
  ],
];

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
        <a href={REPO} target="_blank" rel="noopener noreferrer" className="cf-gh">
          <GitHubMark />
          <span>Star on GitHub</span>
        </a>
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
            <div className="cf-actions">
              <a href="#demo" className="cf-btn cf-btn-solid">
                Try an example
              </a>
              <a href="#how" className="cf-btn">
                How it works
              </a>
            </div>
            <ul className="cf-bullets">
              <li>cites every claim</li>
              <li>abstains when unsure</li>
              <li>plain Python, no framework</li>
            </ul>
          </div>
          <PixelChart />
        </section>

        <section className="cf-demo" id="demo" aria-label="Try WhyBot">
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

        <section className="cf-block cf-how" id="how">
          <div>
            <h2>
              Six steps, <em>the same every time</em>
            </h2>
            <Architecture />
          </div>
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

        <section className="cf-block cf-faq">
          <h2>FAQs</h2>
          <div>
            {FAQS.map(([q, a], i) => (
              <details key={q} open={i === 0}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
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
