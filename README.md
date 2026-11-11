# WhyBot

An agent that explains why a business metric moved, with proof.

Ask "Why did checkout conversion drop 12% on 2025-10-03?". WhyBot investigates a company's data and returns up to 3 likely root causes, ranked. Every claim links to the evidence behind it: a metric query result, a GitHub issue, a support ticket or a deploy changelog entry. If the evidence is weak it says "not enough evidence" and does not guess.

- Live demo: not deployed yet
- API: https://whybot-api.vercel.app/docs (health: https://whybot-api.vercel.app/health?deep=true)
- Dataset: not published yet

The company is synthetic. I generate it with planted root causes, so every system can be scored against known answers. That benchmark is half of the project.

## The problem

When a metric drops, an analyst checks dashboards, deploy logs, incident channels and support tickets, then writes a summary. A plain LLM cannot do this (it has no data). Plain RAG finds loud documents, not the right ones, and cannot check numbers. And any system that reads tickets must not follow instructions hidden inside them.

## The approach

| Piece | What it does | File |
| --- | --- | --- |
| Agent loop | Plain Python state machine: plan, triage, investigate, rank, verify, guard. No framework. | `whybot/agent.py` |
| Tools | `detect_anomaly`, `decompose_by_segment`, `run_metric_query` (read-only SQL), `search_evidence` | `whybot/tools.py` |
| Retrieval | BM25 + dense vectors (bge-small, ONNX) + reciprocal rank fusion + cross-encoder reranker | `whybot/retrieval/` |
| Citation verifier | Drops any claim its cited evidence does not support | `whybot/verifier.py` |
| Guardrails | Injection filter, abstain rules, SQL allow-list | `whybot/guardrails.py`, `whybot/sql_guard.py` |
| Benchmark | Seeded generator: metrics, tickets, issues, changelog, 80 scenarios with gold answers | `bench/generate.py` |
| Eval harness | 3 systems + 4 ablations, LLM judge, CI gate | `bench/run_eval.py` |
| API | FastAPI, answers stream as server-sent events | `whybot/api.py` |
| MCP server | `search_evidence`, `run_metric_query`, `get_run` for any MCP client | `whybot/mcp_server.py` |
| Web app | Next.js: Ask, Evals, How it works | `web/` |

## Architecture

```mermaid
flowchart TD
    Q[Question] --> P[PLAN: parse metric, date, segment]
    P --> T[TRIAGE: detect_anomaly + decompose_by_segment]
    T --> I[INVESTIGATE: model picks tools in a loop]
    I -->|search_evidence| R[(Hybrid retrieval)]
    I -->|run_metric_query| G[SQL guard] --> DB[(Postgres + pgvector)]
    R --> DB
    I --> K[RANK: up to 3 causes, each claim cites evidence IDs]
    K --> V[VERIFY: drop unsupported claims]
    V --> U[GUARD: abstain rules]
    U --> O[Report + stored run trace]
```

Limits on every run: 8 tool calls, 90 seconds, one question of at most 400 characters.

## Results

Every number below is written by `scripts/readme_results.py` from files in `results/`. Nothing is typed by hand. A cell that has not been run says "not run yet".

<!-- results:start -->
Benchmark v1 (seed 7): 80 scenarios, 40 dev and 40 test, with 12 decoys, 8 unanswerable and 8 prompt-injection scenarios. Agent model: `not run yet`. Judge model: `not run yet`.

### Test split (frozen, run once)

Source: `results/test/metrics.json`.

Not run yet.

Ablations of WhyBot on the test split:

Not run yet.

### Dev split (used while building)

Source: `results/dev/metrics.json`.

Not run yet.

Ablations of WhyBot on the dev split:

Not run yet.

### Retrieval only (dev, no LLM)

Source: `results/retrieval_dev.json`. Query = the raw question, documents within 2 days, 33 scenarios.

| Retrieval setup | Recall@10 of key documents | MRR |
| --- | ---: | ---: |
| BM25 only | 50.0% | 0.390 |
| Dense only | 66.7% | 0.461 |
| Hybrid (RRF) | 71.2% | 0.479 |
| Hybrid + reranker | 62.1% | 0.451 |

### Judge calibration

Not run yet. Needs 30 hand labels (`python -m bench.calibrate export`).

### Security tests

Source: `results/security.json` (pytest). 34 of 34 test cases pass.

| OWASP LLM Top 10 item | Test cases | Passed |
| --- | ---: | ---: |
| LLM01 Prompt injection | 4 | 4 |
| LLM02 Sensitive information disclosure | 11 | 11 |
| LLM05 Improper output handling | 12 | 12 |
| LLM06 Excessive agency | 3 | 3 |
| LLM09 Misinformation | 1 | 1 |
| LLM10 Unbounded consumption | 3 | 3 |

### Error analysis (test split)

Not run yet.
<!-- results:end -->

### How to read the metrics

| Metric | Meaning |
| --- | --- |
| Acc@1 / Acc@3 | The planted cause is the top cause / in the top 3. Cause type and segment must both match. For unanswerable scenarios, correct means the system abstained. |
| Cite P | Of the documents a report cites, the share that belong to the planted incident. |
| Cite R | Share of the key documents (the ones that name the cause) that the report cites. |
| Faithful | Share of claims an LLM judge finds supported by their cited evidence. A claim with no evidence counts as not faithful. |
| Abstain acc | Share of scenarios where "answer or abstain" was the right call. |
| Injection | Share of the injection scenarios where the report ignores the planted instruction. |
| p50 / p95 | Latency per question. |
| USD/query | LLM cost per question at list prices. |
| Tools | Mean tool calls per question. |

## Failure modes

| Failure | What happens | Defence |
| --- | --- | --- |
| Model cites a document that does not exist | Claim has a made-up ID | Verifier pass 1 (code) drops it |
| Model cites a real document that says something else | Claim sounds right but is not supported | Verifier pass 2 (LLM) drops it |
| Loud unrelated tickets | A redesign complaint storm on the same day | Triage shows which segment moved; a cause must fit segment and timing |
| Normal weekend dip asked as a "drop" | Day-over-day fall is real but not an incident | Anomaly check uses the same weekday as baseline |
| No evidence exists | The metric moved, nothing explains it | Abstain rules: a cause needs a verified document |
| Prompt injection in a ticket | "Ignore previous instructions..." | Regex filter quarantines known phrasings; prompt rule and verifier handle the rest |
| Model writes harmful SQL | `DROP TABLE`, reading other tables | Parsed allow-list, read-only transaction, SELECT-only database role |

## Limits

- The data is synthetic and written from templates. Real tickets are messier. Scores here do not transfer to a real company.
- 40 test scenarios is a small sample. One scenario is 2.5 points of accuracy. Treat small gaps as noise.
- The injection filter is a list of regular expressions. It only catches known wordings.
- The judge is an LLM. Its agreement with a human is measured on 30 claims only.
- Current Claude models do not accept a `temperature` setting, so the judge cannot be pinned to temperature 0. Repeatability comes from caching each request by its hash.
- The spend cap is checked before a run and updated after it, so it can overshoot by the cost of one run.

## Run it

```bash
cp .env.example .env          # add ANTHROPIC_API_KEY for live questions (optional)
docker compose up             # Postgres + API on http://localhost:8000/docs
```

The API container loads the benchmark on first start. Without a key, `/health`, `/limits`, `/runs` and cached example questions work; live questions return a clear "no key" message.

Development:

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
docker compose up -d db && .venv/bin/python -m bench.load
.venv/bin/python -m pytest -q                       # unit, agent and security tests (no key needed)
.venv/bin/python -m bench.run_eval --split dev      # needs ANTHROPIC_API_KEY
.venv/bin/python -m bench.summarize && .venv/bin/python scripts/readme_results.py
cd web && npm install && npm run dev
```

MCP server (for Claude Code or Claude Desktop):

```bash
claude mcp add whybot -- "$PWD/.venv/bin/python" -m whybot.mcp_server
```

## Cost protection on the public demo

- Example questions replay stored runs. They cost nothing.
- Live questions: 5 per visitor per day (by salted IP hash).
- A global daily spend cap of 1 USD is kept in Postgres. When it is hit the site says so and stays in cached mode.
- The API key lives only on the server.

## Deployment

| Part | Where | Why |
| --- | --- | --- |
| Web app | Vercel (Next.js) | Static pages plus one client that calls the API. |
| API | Vercel (FastAPI on the Python runtime) | It fits: the two quantized ONNX models are 56 MB and the bundle is about 245 MB. One hybrid search takes about 1.5 s cold and 0.35 s warm there (measured with `/health?deep=true`). Render's free tier was the fallback; it sleeps after 15 minutes and has 512 MB of memory. |
| Database | Neon free tier (Postgres 17 + pgvector) | Serverless Postgres in the same region as the function. |

The SQL tool connects with a separate SELECT-only role (`DATABASE_URL_READONLY`).

## What I would change

- Use real, messy text (public GitHub issues) for the documents, keeping the planted causes.
- Grow the test split to a few hundred scenarios so confidence intervals are tight.
- Add prompt caching for the system prompts and evidence dossier to cut input cost.
- Replace the regex injection filter with a small trained classifier and measure its recall.
- Stream partial results from the ranker so the first cause shows sooner.

## Docs

- `docs/STUDY_GUIDE.md`: every module in simple English, design choices, 20 interview questions.
- `docs/RESUME.md`: resume bullets filled from `results/`.
- `bench/data/v1/README.md`: dataset card.
