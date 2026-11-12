// The whole site is this one page: a short hello, the working demo, three numbers, six steps.
// Every number comes from src/data/summary.json. None is typed by hand.

import type { Metadata } from "next";
import { Figtree, Fraunces } from "next/font/google";
import type { ReactNode } from "react";
import { AskClient } from "../components/ask/AskClient";
import { fmtPercent, fmtSeconds } from "../lib/format";
import { summary } from "../lib/summary";
import "./landing.css";

const display = Fraunces({ subsets: ["latin"], variable: "--font-display" });
const body = Figtree({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "WhyBot - find out why a metric moved",
};

type Sys = { system: string; metrics?: Record<string, number | null> | null };

function metric(system: string, key: string): number | null {
  const rows = (summary.splits?.test?.systems ?? []) as Sys[];
  return rows.find((r) => r.system === system)?.metrics?.[key] ?? null;
}

function Mascot() {
  // "Why", the investigator: a round robot with a red cap and a magnifying glass.
  return (
    <svg viewBox="0 0 320 340" className="cf-mascot" role="img" aria-label="WhyBot, a small robot detective holding a magnifying glass">
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
};

const STEPS: [string, string, string, string][] = [
  ["plan", "sky", "Plan", "Read the question. Pick the metric and the day."],
  ["triage", "mint", "Triage", "Is the day unusual? Which segment moved?"],
  ["investigate", "sun", "Investigate", "Search tickets, issues and deploys. Query the metrics."],
  ["rank", "rose", "Rank", "Write up to three causes, each with its evidence."],
  ["verify", "mint", "Verify", "Check every sentence against what it cites."],
  ["guard", "sky", "Guard", "No solid proof? Say \"not enough evidence\"."],
];

export default function HomePage() {
  const tests = summary.benchmark?.test;
  return (
    <div className={`cf-page ${display.variable} ${body.variable}`}>
      <main id="main">
        <section className="cf-hero">
          <div className="cf-hero-text">
            <p className="cf-brand">
              <span aria-hidden="true">?</span> WhyBot
            </p>
            <h1>
              Ask why a number moved. <em>Get the cause, with proof.</em>
            </h1>
            <p className="cf-lede">
              I check the data, read the tickets and the deploy log, and show the evidence behind every sentence. If I am not
              sure, I say so.
            </p>
          </div>
          <div className="cf-hero-art">
            <Mascot />
          </div>
        </section>

        <section className="cf-demo" aria-label="Try WhyBot">
          <AskClient hideIntro />
        </section>

        <section className="cf-stats" aria-label="Test results">
          <div className="cf-stat cf-tone-sun">
            <strong>{fmtPercent(metric("whybot", "accuracy_at_1"))}</strong>
            <span>right cause found</span>
          </div>
          <div className="cf-stat cf-tone-mint">
            <strong>{fmtPercent(metric("whybot", "citation_precision"))}</strong>
            <span>of cited documents were the right ones</span>
          </div>
          <div className="cf-stat cf-tone-sky">
            <strong>{fmtSeconds(metric("whybot", "latency_p50_s"))}</strong>
            <span>median time per question</span>
          </div>
        </section>
        <p className="cf-caveat">
          Measured once on {tests} held-out cases from a synthetic company. A model alone finds{" "}
          {fmtPercent(metric("llm_only", "accuracy_at_1"))}; plain document search finds {fmtPercent(metric("rag", "accuracy_at_1"))}.
        </p>

        <section className="cf-section">
          <h2>How it works</h2>
          <ol className="cf-steps">
            {STEPS.map(([icon, tone, name, text]) => (
              <li key={name}>
                <span className={`cf-icon cf-tone-${tone}`} aria-hidden="true">
                  <svg viewBox="0 0 32 32">{ICONS[icon]}</svg>
                </span>
                <h3>{name}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="cf-footer">Synthetic data. No real company or customer appears on this site.</footer>
    </div>
  );
}
