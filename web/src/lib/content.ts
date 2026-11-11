// All site copy lives here. Edit this file to change wording.
// Rules: simple English, short sentences, hyphens (no em dashes), no emoji.
// No benchmark numbers here. Numbers come from src/data/summary.json.

import type { MetricKind } from "./format";

export const site = {
  name: "WhyBot",
  tagline: "Cited root-cause analysis for metric changes",
  description:
    "WhyBot is an AI agent that investigates why a business metric moved. It returns up to 3 ranked root causes, and every claim links to evidence.",
  footer: "Synthetic data. Built by Krushal Kalkani.",
  nav: [
    { href: "/", label: "Ask" },
    { href: "/evals", label: "Evals" },
    { href: "/how-it-works", label: "How it works" },
  ],
};

export const ask = {
  heading: "Ask why a metric moved",
  intro:
    "WhyBot investigates a synthetic e-commerce company. It queries metrics, searches the changelog, GitHub issues and support tickets, and returns up to 3 ranked root causes. Every claim links to evidence. If the evidence is weak, it says so.",
  inputLabel: "Your question",
  placeholder: "Why did checkout conversion drop 12% on 2025-10-03?",
  submit: "Investigate",
  stop: "Stop",
  examplesHeading: "Try a stored example",
  examplesNote: "Examples replay a saved run. They make zero API calls.",
  traceHeading: "Step trace",
  traceEmpty: "Pick an example or ask a question. Each agent step will show up here.",
  traceNote: "Open a step to see its input, output, latency, tokens and cost.",
  reportHeading: "Report",
  reportEmpty: "The report appears here when the investigation ends.",
  reportPending: "Investigating. The report appears when all steps finish.",
  verdictAnswered: "Answered",
  verdictInsufficient: "Not enough evidence",
  verdictInsufficientNote:
    "The agent did not find evidence strong enough to name a root cause. It abstains instead of guessing.",
  causesHeading: "Ranked root causes",
  evidenceHeading: "Evidence",
  evidenceNote: "Click an evidence chip in a claim to jump to its card.",
  droppedHeading: "Dropped claims",
  droppedNote: "The citation verifier removed these claims. The cited evidence did not support them.",
  notesHeading: "Notes",
  fixtureNote: "Placeholder data. This run is a hand-written fixture, not real agent output.",
  quarantinedBadge: "Quarantined",
  quarantinedNote: "This text looked like a prompt injection. It was withheld from the model.",
  shareLabel: "Copy share link",
  shareCopied: "Link copied",
  mode: {
    loading: "Checking the live API...",
    live: (remaining: number, limit: number) =>
      `Live mode - ${remaining} of ${limit} live questions left today for you.`,
    disabled:
      "Cached mode - the live API is not configured for this site. Stored examples still work.",
    unreachable: "Cached mode - the live API is unreachable right now. Stored examples still work.",
    capReached:
      "Cached mode - the daily spend cap is reached. Live questions are paused until tomorrow. Stored examples still work.",
    noneLeft: (limit: number) =>
      `Cached mode - you used all ${limit} live questions for today. Stored examples still work.`,
    liveOff: "Cached mode - live questions are turned off. Stored examples still work.",
  },
  errors: {
    rate_limited: "You reached the daily limit for live questions. Stored examples still work.",
    spend_cap: "The daily spend cap is reached. Stored examples still work.",
    no_llm: "The model is not available right now. Stored examples still work.",
    bad_request: "The API rejected this question. Try rewording it.",
    timeout: "The investigation timed out.",
    internal: "The agent hit an internal error.",
    unreachable: "The live API could not be reached. Stored examples still work.",
    not_found: "This run was not found.",
    disabled: "The live API is not configured for this site. Stored examples still work.",
    runNeedsApi:
      "This link points to a stored run, but the live API is not configured. Stored examples still work.",
  },
};

export const stepKindLabels: Record<string, string> = {
  plan: "Plan",
  tool: "Tool",
  llm: "LLM",
  rank: "Rank",
  verify: "Verify",
  guard: "Guard",
};

export const causeTypeLabels: Record<string, string> = {
  bad_deploy: "Bad deploy",
  pricing_change: "Pricing change",
  regional_outage: "Regional outage",
  platform_bug: "Platform bug",
  campaign_end: "Campaign end",
  payment_provider_error: "Payment provider error",
  seasonality: "Seasonality",
};

export const sourceLabels: Record<string, string> = {
  changelog: "Changelog",
  issue: "Issue",
  ticket: "Ticket",
  metric: "Metric",
};

// ---------------------------------------------------------------------------
// Evals page
// ---------------------------------------------------------------------------

export interface MetricDef {
  key: string;
  label: string;
  kind: MetricKind;
  definition: string;
}

export const metricDefs: MetricDef[] = [
  {
    key: "accuracy_at_1",
    label: "Acc@1",
    kind: "percent",
    definition:
      "Share of answerable scenarios where the top ranked cause matches the true cause type and segment.",
  },
  {
    key: "accuracy_at_3",
    label: "Acc@3",
    kind: "percent",
    definition: "Share of answerable scenarios where the true cause is anywhere in the top 3.",
  },
  {
    key: "citation_precision",
    label: "Cite precision",
    kind: "percent",
    definition: "Of all evidence ids the system cited, the share that are truly relevant to the scenario.",
  },
  {
    key: "citation_recall",
    label: "Cite recall",
    kind: "percent",
    definition: "Of all evidence documents that are truly relevant, the share the system cited.",
  },
  {
    key: "faithfulness",
    label: "Faithfulness",
    kind: "percent",
    definition: "Share of claims that an LLM judge rates as supported by the evidence they cite.",
  },
  {
    key: "abstention_accuracy",
    label: "Abstention",
    kind: "percent",
    definition:
      'Share of scenarios where the system made the right call between answering and saying "not enough evidence".',
  },
  {
    key: "injection_resistance",
    label: "Injection resist.",
    kind: "percent",
    definition:
      "Share of prompt-injection scenarios where the planted instruction did not change the answer.",
  },
  {
    key: "latency_p50_s",
    label: "p50 latency",
    kind: "seconds",
    definition: "Median end-to-end time per question, in seconds.",
  },
  {
    key: "latency_p95_s",
    label: "p95 latency",
    kind: "seconds",
    definition: "95th percentile end-to-end time per question, in seconds.",
  },
  {
    key: "cost_per_query_usd",
    label: "Cost / query",
    kind: "usd",
    definition: "Mean model API cost per question, in US dollars.",
  },
  {
    key: "mean_tool_calls",
    label: "Tool calls",
    kind: "count",
    definition: "Mean number of tool calls per question.",
  },
];

export const evals = {
  heading: "Evals",
  intro:
    "Results on a synthetic benchmark of root-cause scenarios. Every number on this page is read from one results file. Nothing is typed in by hand. A cell that says \"not run yet\" has no result so far.",
  benchmarkHeading: "Benchmark",
  benchmarkLabels: {
    version: "Version",
    seed: "Seed",
    scenarios: "Scenarios",
    dev: "Dev split",
    test: "Test split",
    decoys: "With decoys",
    unanswerable: "Unanswerable",
    injection: "Prompt injection",
    cause_types: "Cause types",
  } as Record<string, string>,
  modelsHeading: "Models",
  tables: {
    mainTest: {
      title: "Main comparison - test split",
      how: "Rows are systems. Columns are metrics. Higher is better for the percent columns. Lower is better for latency, cost and tool calls. The test split is held out. It is run once, after all tuning is done on the dev split.",
    },
    mainDev: {
      title: "Main comparison - dev split",
      how: "Same layout as the test table. The dev split is used for tuning prompts and settings, so these numbers are optimistic. Trust the test table more.",
    },
    ablation: {
      title: "Ablations",
      how: "Each row is the full WhyBot system with one part removed or swapped. Compare each row with row C in the main table for the same split. A big drop means that part matters.",
    },
    retrieval: {
      title: "Retrieval recall",
      how: "Each row is a retrieval setup. Recall@10 is the share of queries where a relevant document is in the top 10 results. MRR is the mean of 1 / rank of the first relevant document. Higher is better for both.",
    },
    judge: {
      title: "Judge calibration",
      how: "The faithfulness metric uses an LLM judge. This table checks the judge against human labels on a sample. Agreement is the share of matching labels. Cohen's kappa corrects agreement for chance. 1 is perfect and 0 is chance level.",
    },
    security: {
      title: "Security tests",
      how: "Each row is one adversarial test, mapped to an OWASP Top 10 for LLM Applications category. A test passes when the attack does not change the agent's behavior or output.",
    },
    errors: {
      title: "Error analysis",
      how: "Failed scenarios grouped by failure type. Count is the number of failures in the group. Example ids point to benchmark scenarios. Fix is the planned or shipped change.",
    },
  },
  definitionsHeading: "Metric definitions",
  systemsHeading: "Systems compared",
  systems: [
    { label: "A. LLM only", text: "The model answers from the question alone. No tools and no retrieval." },
    {
      label: "B. Vector RAG, no tools",
      text: "Dense retrieval over documents, then one model call. It cannot query metrics.",
    },
    {
      label: "C. WhyBot (full)",
      text: "The full agent: metric tools, hybrid retrieval with reranking, citation verifier and guardrails.",
    },
  ],
};

// ---------------------------------------------------------------------------
// How it works page
// ---------------------------------------------------------------------------

export const howItWorks = {
  heading: "How it works",
  intro:
    "WhyBot is a tool-using agent with a fixed pipeline around it. The model plans and reasons. Plain code checks its work. A claim reaches the report only if its citation survives verification.",
  diagramHeading: "Architecture",
  diagramNote: "A question flows top to bottom. Side boxes are the services each stage uses.",
  pipeline: [
    {
      id: "question",
      title: "Question",
      text: 'For example: "Why did checkout conversion drop 12% on 2025-10-03?"',
      items: [],
    },
    {
      id: "planner",
      title: "Planner",
      text: "Reads the question. Picks the metric, the date and a plan.",
      items: [],
      uses: "Claude API",
    },
    {
      id: "triage",
      title: "Triage",
      text: "Confirms the change is real and finds where it is.",
      items: ["detect_anomaly", "decompose_by_segment"],
      uses: "Postgres",
    },
    {
      id: "investigate",
      title: "Investigate loop",
      text: "The agent calls tools until it has enough evidence. Bounded by a max step count and a timeout.",
      items: ["search_evidence", "run_metric_query"],
      uses: "Hybrid retrieval, Postgres, Claude API",
      loop: true,
    },
    {
      id: "rank",
      title: "Rank hypotheses",
      text: "Keeps up to 3 causes, ordered by how well the evidence supports them.",
      items: [],
      uses: "Claude API",
    },
    {
      id: "verify",
      title: "Citation verifier",
      text: "Checks each claim against the evidence it cites. Unsupported claims are dropped.",
      items: [],
    },
    {
      id: "guard",
      title: "Guardrails",
      text: "Quarantines text that looks like a prompt injection. Abstains when the evidence is weak.",
      items: [],
    },
    {
      id: "report",
      title: "Report",
      text: 'Up to 3 ranked causes with cited claims, or "not enough evidence".',
      items: [],
    },
  ],
  services: [
    {
      title: "Postgres + pgvector",
      text: "One database for everything.",
      items: ["metrics", "documents", "chunks", "runs"],
    },
    {
      title: "Hybrid retrieval",
      text: "Two searches, fused, then reranked.",
      items: [
        "BM25 + dense (bge-small, ONNX)",
        "reciprocal rank fusion",
        "cross-encoder reranker",
      ],
    },
    {
      title: "Claude API",
      text: "Planning, tool choice and ranking. Called from the server only.",
      items: [],
    },
    {
      title: "MCP server",
      text: "Exposes the same tools over the Model Context Protocol, so other clients can use them.",
      items: [],
    },
  ],
  sections: [
    {
      id: "failure-modes",
      title: "Failure modes",
      intro: "Where the system goes wrong, and what limits the damage.",
      bullets: [
        "Decoy evidence - a document that looks related but is about another segment or date. The verifier and the segment check catch many of these, not all.",
        "Wrong segment - the agent blames the right kind of cause in the wrong region, platform or channel.",
        "Over-abstention - the agent says \"not enough evidence\" when the evidence was there but retrieval missed it.",
        "Under-abstention - the agent names a cause for a change that is only noise.",
        "Prompt injection - a ticket or issue contains instructions aimed at the model. Suspect text is quarantined and shown with a badge.",
        "Tool errors and timeouts - a failed step is marked in the trace. The agent continues with what it has.",
      ],
    },
    {
      id: "limits",
      title: "Limits",
      intro: "What this project does not claim.",
      bullets: [
        "All data is synthetic. Real company data is messier.",
        "It answers one kind of question: why one metric moved on one date.",
        "There are 7 known cause types. A cause outside that list will not be named.",
        "The verifier checks that a citation supports a claim. It does not prove the claim is the true cause.",
        "The benchmark is small. Small differences between systems may be noise.",
        "Questions are capped at 400 characters, and each run has a step limit and a timeout.",
      ],
    },
    {
      id: "cost-protection",
      title: "Cost protection",
      intro: "This is a public demo backed by a paid model API. These controls keep the bill bounded.",
      bullets: [
        "Examples are cached runs. Replaying one makes zero API calls.",
        "Live questions are limited to 5 per IP address per day.",
        "A global daily spend cap is stored in the database. When it is hit, the site switches to cached mode.",
        "API keys stay on the server. They never reach the browser.",
      ],
    },
    {
      id: "benchmark",
      title: "The benchmark",
      intro: "How the system is measured.",
      bullets: [
        "80 synthetic scenarios, each with a known root cause.",
        "40 dev scenarios for tuning and 40 test scenarios held out for the final run.",
        "Decoy scenarios include plausible but wrong evidence.",
        "Unanswerable scenarios have no real cause. The right output is \"not enough evidence\".",
        "Prompt-injection scenarios plant instructions inside tickets or issues.",
        "Results, with baselines and ablations, are on the Evals page.",
      ],
    },
  ],
};
