# WhyBot study guide

Read this before WhyBot goes on your resume. It explains every module in simple English, why each design choice was made, what was rejected, and 20 questions an interviewer may ask.

All numbers live in `README.md` (the Results section) and `results/`. This guide points to them and does not repeat them, so it cannot go stale.

## 1. The one-minute story

A metric moved. Someone asks why. WhyBot does what an analyst does:

1. Check if the day is really unusual.
2. Find which region, platform or channel moved.
3. Look for deploys, incidents and customer tickets near that day.
4. Write up to 3 causes. Each sentence points to its evidence.
5. Check each sentence against its evidence. Remove the ones that fail.
6. If nothing solid is left, say "not enough evidence".

The company is fake and built by a script with planted causes. So I know the right answer for each question and can score any system.

## 2. Walk through one request

File: `whybot/agent.py`. The loop is a state machine. `Agent.run` holds a dict from state to handler and runs `state = yield from handlers[state](run)` until the state is `DONE`.

| State | LLM call? | What happens | Next |
| --- | --- | --- | --- |
| PLAN | yes, structured output `Plan` | Parse the question into metric, date, segment. List steps. | TRIAGE (or GUARD if the date is outside the data) |
| TRIAGE | no | Code always runs `detect_anomaly` and `decompose_by_segment`. | INVESTIGATE |
| INVESTIGATE | yes, with tools | The model picks tools. Results go back as `tool_result` blocks. Stops when the model stops calling tools, or at 8 tool calls, or at 60% of the time budget. | RANK |
| RANK | yes, structured output `DraftReport` | Up to 3 causes. Each claim lists evidence IDs. | VERIFY |
| VERIFY | yes (one call) | Code check, then LLM check of every claim. | GUARD |
| GUARD | no | Abstain rules in plain code. | DONE |

Each handler is a Python generator. It yields `Step` objects. The API streams each step to the browser the moment it happens, and stores it in the `tool_traces` table with latency, tokens and cost.

`Run` (a dataclass) holds all state of one investigation: the plan, every piece of evidence by ID, the draft, the kept causes, the dropped claims, the notes.

Why triage is code and not the model's choice: every investigation needs those two checks. Running them in code means they cannot be skipped, and it saves two LLM turns.

## 3. Every module

| File | In simple English |
| --- | --- |
| `whybot/schemas.py` | All data shapes as Pydantic models: tool inputs and outputs, what the LLM must write (`Plan`, `DraftReport`, `VerifierOutput`), the final `Report`, a `Step`. One contract for the API, the evals and the web app. |
| `whybot/config.py` | Reads env vars. `RetrievalConfig` and `AgentConfig` hold the switches the ablations flip. |
| `whybot/db.py` | Opens a Postgres connection with psycopg. No ORM, so every SQL statement is visible. |
| `whybot/schema.sql` | Tables: `daily_metrics`, `documents`, `chunks` (with a 384-number vector), `runs`, `tool_traces`, `spend_daily`, `ask_counts`. |
| `whybot/llm.py` | Thin wrapper on the Claude Messages API. Adds cost, latency, structured output, and a disk cache keyed by a hash of the request. |
| `whybot/prompts.py` | Every prompt in one file. Also `render_evidence`, which wraps a document in an `<evidence>` tag and escapes angle brackets. |
| `whybot/tools.py` | The four tools and the registry `TOOLS`. Also `robust_z`, the anomaly maths. |
| `whybot/sql_guard.py` | Parses model-written SQL and allows only one SELECT over `daily_metrics`. |
| `whybot/retrieval/bm25.py` | Keyword search written by hand (about 60 lines). |
| `whybot/retrieval/onnx_models.py` | Loads the embedding model and the reranker with ONNX Runtime. |
| `whybot/retrieval/search.py` | The hybrid pipeline: BM25 + dense, reciprocal rank fusion, rerank, best passage per document. |
| `whybot/verifier.py` | Checks each claim against its cited evidence. |
| `whybot/guardrails.py` | Injection regex filter and the abstain rules. |
| `whybot/agent.py` | The state machine described above. |
| `whybot/baselines.py` | System A (LLM only) and system B (plain vector RAG). |
| `whybot/limits.py` | Per-IP daily limit and the global daily spend cap, stored in Postgres. |
| `whybot/store.py` | Saves and loads runs. Finds a cached run for a repeated question. |
| `whybot/api.py` | FastAPI app. `POST /ask` streams server-sent events. |
| `whybot/mcp_server.py` | Exposes three tools over the Model Context Protocol (stdio). |
| `bench/generate.py`, `bench/templates.py` | The seeded benchmark generator and its text templates. |
| `bench/load.py` | Loads the benchmark into Postgres. Creates the read-only database role. |
| `bench/run_eval.py` | Runs systems over scenarios, writes per-scenario records and `metrics.json`. |
| `bench/metrics.py` | Pure scoring functions. |
| `bench/judge.py` | LLM judge for faithfulness. |
| `bench/calibrate.py` | Builds the hand-labelling page and computes judge-vs-human agreement. |
| `bench/retrieval_eval.py` | Retrieval-only recall@10 and MRR. |
| `bench/gate.py` | CI gate: fails if accuracy@1 or citation precision drops more than 5 points. |
| `bench/summarize.py`, `scripts/readme_results.py` | Collect results into `results/summary.json` and write the README tables from it. |

## 4. The tools

| Tool | Input | What it returns | Key idea |
| --- | --- | --- | --- |
| `detect_anomaly` | metric, date, optional segment | value, baseline, percent change, z-score, verdict | Baseline = median of the same weekday in the 6 weeks before. So a normal Saturday is not an anomaly. |
| `decompose_by_segment` | metric, date | change per region, platform, channel | A slice is "concentrated" if it moved 8+ points more than the median of its siblings and its own z is 3 or more. |
| `run_metric_query` | SQL text | rows (max 200) | Model-written SQL passes three safety layers. |
| `search_evidence` | query, date range, source, k | evidence cards | Hybrid retrieval. |

Robust z-score (`robust_z` in `whybot/tools.py`): `z = (value - median) / spread`, where spread is 1.4826 x the median absolute deviation, with a floor of 1% of the median. Median and MAD ignore a few odd past days. That matters here because earlier incidents sit inside the history window. Mean and standard deviation would be pulled by them.

## 5. Retrieval

Pipeline (`Retriever.search` in `whybot/retrieval/search.py`):

1. BM25 over passages in memory. Good at exact words: service names, versions, "declined".
2. Dense search. The query is embedded with bge-small (384 numbers). Postgres with pgvector returns the nearest passages by cosine distance (`<=>`). Good at meaning: "cannot pay" matches "card declined".
3. Reciprocal rank fusion. Each item scores `1 / (60 + rank)` in each list, and the scores are added. It uses ranks only, so BM25 scores and cosine similarities do not need to be on the same scale.
4. Cross-encoder reranker on the top 20. It reads the query and passage together, so it is more accurate than comparing two separate vectors, and slower.
5. Keep the best passage per document. Return the top k.

No vector index is used. There are about 4,000 passages, so an exact scan takes a few milliseconds and has perfect recall. With millions of rows I would add an HNSW index and accept approximate results.

Honest finding: in the retrieval-only test (`results/retrieval_dev.json`, table in the README) the reranker lowered recall@10 compared with plain fusion. The query there is the raw question ("Why did orders drop 6%..."). The reranker scores how well a passage answers that sentence, and customer tickets match it better than a changelog line such as "End of Spring Savings campaign". Inside the agent the queries are different (the model writes targeted ones), so check the ablation row "C without reranker" in the README for the end-to-end effect. Report both. Do not claim the reranker helps unless that row shows it.

## 6. Verifier and guardrails

Verifier (`whybot/verifier.py`), two passes:

1. Code: every cited ID must be evidence this run retrieved and must not be quarantined. Catches made-up IDs. Free and exact.
2. LLM: one call lists each claim next to its cited text and returns supported or not. Catches a real citation that does not say what the claim says.

Failed claims move to `dropped_claims`. A cause that lost claims has its confidence capped at medium.

Abstain rules (`apply_abstain_rules` in `whybot/guardrails.py`), in code:

- If the ranker said abstain, abstain.
- A cause with no surviving claim is dropped.
- A cause must cite at least one real document. Seasonality is the exception: it must cite metric evidence.
- If the top cause has low confidence, abstain.
- No causes left means the verdict is "insufficient_evidence".

Prompt injection, three layers:

1. `looks_like_injection`: regular expressions for known wordings. A matching document is quarantined: its text is withheld from the model and it cannot be cited.
2. Prompt rule: evidence sits inside `<evidence>` tags, and the system prompt says that text is data, never instructions. `render_evidence` escapes `<` and `>` so a document cannot close the tag.
3. The verifier: "this ticket says the cause is X" does not support the claim "the cause is X".

The benchmark has two obvious injection templates (the regex catches them) and two subtle ones with no trigger words (only layers 2 and 3 can stop them). This keeps the score honest: I wrote both the attacks and the filter, so a filter-only test would always pass.

SQL safety, three layers:

1. `check_sql`: parse with sqlglot. One statement, SELECT or UNION only, tables from an allow-list, no schema-qualified names, no unknown functions. The SQL that runs is rebuilt from the parse tree without comments, wrapped in `SELECT * FROM (...) LIMIT 201`.
2. `SET TRANSACTION READ ONLY` and a 3 second statement timeout.
3. The connection logs in as a role that can only SELECT from `daily_metrics`.

## 7. The benchmark

File: `bench/generate.py`. Seed 7. Same seed, same files on the same machine type (a unit test checks this). I learned in CI that Linux and macOS give slightly different random draws, so the committed files are the benchmark and CI checks their SHA-256 hashes (`bench/verify_data.py`).

- Metrics: 731 days x 5 regions x 3 platforms x 4 channels. A funnel: sessions, checkout starts, payment attempts, failures, orders, revenue. Weekly pattern, slow growth, random noise.
- An incident changes one funnel rate for one segment for a few days. Example: a payment provider error sets the failure rate to 20-45% in one region.
- Documents: routine tickets, deploys and issues every day (noise), plus the documents for each incident.
- 80 scenarios, one every 8 days. The first 40 (2024) are dev. The last 40 (2025) are test. The split is by time, like real life.

| Kind | Count | What it tests |
| --- | ---: | --- |
| plain | 52 | Find the planted cause among 6 types |
| decoy_loud | 6 | A real cause plus a loud unrelated event on the same day |
| decoy_seasonal | 6 | A normal weekend dip asked as a "drop". Right answer: seasonality |
| unanswerable | 8 | The metric moved but no document explains it. Right answer: abstain |
| injection | 8 | A real cause plus tickets that try to hijack the model |

Each scenario stores the planted cause, `key_evidence_ids` (documents that name the cause) and `gold_evidence_ids` (key documents plus supporting tickets).

Rules I followed: prompts were tuned on dev only. The test split was run once. `bench/run_eval.py` refuses to run it again without `--force`.

## 8. Evaluation

Three systems: A = LLM only. B = plain vector RAG (dense top 8, no date filter, one call). C = WhyBot. Four ablations of C: no reranker, no verifier, BM25 only, dense only.

Metric definitions are in the README and in `bench/metrics.py`. The strict part: accuracy needs the cause type and the segment to match.

The judge (`bench/judge.py`) is a stronger model than the agent. It rates each claim against its cited evidence. I hand-label 30 claims and report agreement and Cohen's kappa. Note the judge and WhyBot's own verifier do a similar job with different models and prompts. So WhyBot's faithfulness score partly measures "two LLM checks agree". The hand labels are the real anchor.

The LLM cache: every request is hashed (model, system prompt, messages, tools, schema, effort). The response is stored under that hash. Re-running an eval replays stored answers, costs nothing and gives the same numbers. The CI gate replays the 20-scenario smoke subset from a committed cache, so CI needs no API key. If a prompt changes, the hash changes, the replay fails with a clear error, and I must re-run locally and commit the new cache.

## 9. Design choices and what I rejected

| Choice | Rejected alternative | Why |
| --- | --- | --- |
| Plain Python state machine | LangChain, LlamaIndex, an SDK tool runner | I can explain every line. Fixed states make limits, logging and tests simple. A framework hides the loop. |
| Triage in code, then a model-driven loop | Let the model decide everything | The two checks are always needed. Code cannot forget them. |
| Hybrid retrieval | Dense only, or BM25 only | Tickets use customer words (dense helps). Changelogs use exact names and versions (BM25 helps). The ablations measure each. |
| Reciprocal rank fusion | Weighted sum of scores | Scores are on different scales. RRF needs no tuning. |
| Exact vector scan in pgvector | HNSW index, or a separate vector database | 4,000 rows. Exact is fast and has full recall. One database is simpler to run. |
| Small ONNX models on CPU | An embeddings API, or PyTorch | No extra key or cost. ONNX Runtime is far smaller than PyTorch, so it fits a serverless function. |
| Separate verifier call | Trust the ranker's citations | A second pass with only the claim and its evidence is harder to fool and is easy to ablate. |
| Abstain rules in code | Ask the model to be careful | Rules are testable and do not drift. |
| Parsed SQL allow-list + read-only role | Keyword block-list | Block-lists are easy to bypass and block harmless text. Defence in depth: if the parser check fails, the database still refuses. |
| Synthetic benchmark with planted causes | Real incident data | I need known answers to score against. Real data has no ground truth and cannot be shared. The cost: templated text is cleaner than reality. |
| Split by time | Random split | Matches real use: tune on the past, test on the future. |
| Sonnet as judge, Haiku as agent | Same model for both | The judge should be stronger than what it grades. |
| Request-hash cache | "temperature 0" | Current Claude models reject a temperature setting. A cache gives exact repeatability. |
| Server-sent events | WebSockets or polling | One-way stream over plain HTTP. Works with FastAPI `StreamingResponse` and `fetch`. |
| Spend cap and rate limit in Postgres | In-memory counters | Serverless instances do not share memory. |

## 10. Twenty interview questions

1. **Walk me through the agent loop.**
   Six states in `whybot/agent.py`: PLAN, TRIAGE, INVESTIGATE, RANK, VERIFY, GUARD. `Agent.run` maps each state to a handler and loops until DONE. Handlers are generators that yield `Step` objects and return the next state. Only INVESTIGATE is model-driven; the rest is a fixed pipeline.

2. **Why no LangChain?**
   The loop is about 300 lines. Writing it myself means I control limits, errors, logging and cost tracking, and I can test it with a scripted fake model (`tests/fakes.py`). The trade-off: I maintain the tool-calling plumbing myself.

3. **How does tool calling work at the API level?**
   I send tool definitions (name, description, JSON schema from the Pydantic input model, see `Tool.claude_spec`). The model replies with `tool_use` blocks. I append the assistant message unchanged, run each tool, and send one user message with a `tool_result` per `tool_use`, matched by `tool_use_id`. See `_investigate` and `_call_tool`.

4. **What if the model sends bad tool input?**
   `_call_tool` validates with Pydantic. A validation error, a rejected SQL statement or a database error becomes a `tool_result` with `is_error: true` and a short message. The model can fix its call. Test: `test_bad_tool_input_comes_back_as_error_result`.

5. **How do you stop the agent from running forever or costing too much?**
   Max 8 tool calls, a time budget, one question up to 400 characters, 5 live questions per IP per day, and a global daily spend cap in Postgres (`whybot/limits.py`). Tests: `test_tool_budget_stops_a_model_that_never_stops`, `test_per_ip_daily_limit_and_spend_cap`.

6. **Why hybrid retrieval? Did it help?**
   BM25 catches exact names and versions; dense catches paraphrase. I measured it two ways: retrieval-only recall@10 (`results/retrieval_dev.json`) and end-to-end ablations (README). Quote those tables. If an ablation shows a part did not help, say so.

7. **Explain reciprocal rank fusion.**
   For each ranked list, an item gets `1 / (60 + rank)`. Add across lists. Items found by both lists rise. It ignores raw scores, so no normalisation is needed. Code: `reciprocal_rank_fusion`, 6 lines.

8. **What is a cross-encoder and why is it slower?**
   A bi-encoder embeds query and passage separately; comparing is one dot product. A cross-encoder feeds both texts through the model together, so it needs one forward pass per pair. More accurate, so I use it only on the top 20.

9. **Did the reranker help?**
   Not in the retrieval-only test with raw questions: recall@10 went down (see README). I explain why in section 5. The end-to-end answer is the "C without reranker" row. I report what the data shows.

10. **How does the citation verifier work, and what does it miss?**
    Pass 1 is code: cited IDs must be retrieved evidence. Pass 2 is one LLM call that judges each claim against its cited text. It can miss a wrong claim if the verifier model makes the same mistake as the ranker, and it does not check that the causes are complete. The "C without verifier" row shows its measured effect.

11. **How do you defend against prompt injection?**
    Three layers: regex quarantine, evidence-as-data prompt rule with escaped tags, and the verifier. Plus the model has only read tools and the SQL role is read-only, so a successful injection cannot change data. The benchmark measures it with obvious and subtle attacks. The regex alone would be a weak defence and I say so.

12. **How is the SQL tool made safe?**
    Parse to a syntax tree and allow one SELECT over an allow-list; run in a read-only transaction with a timeout; connect as a SELECT-only role. Three layers, tested in `tests/test_security.py`.

13. **How do you know the agent is right? What is ground truth?**
    The generator plants each cause and writes the documents, so each scenario has a known cause type, segment and gold document IDs. Accuracy needs type and segment to match.

14. **Is a synthetic benchmark valid?**
    It is valid for comparing systems on the same task and for catching regressions. It is not evidence about real-company accuracy: the text is templated and I designed both the task and the solver. I state that limit in the README.

15. **How did you avoid tuning on the test set?**
    Dev and test are split by time. Prompts were changed only after dev runs. The test split was run once; the script refuses a second run without `--force`. With 40 scenarios, one scenario is 2.5 points, so I do not read much into small gaps.

16. **How do you evaluate faithfulness, and can you trust an LLM judge?**
    A stronger model rates each claim against its evidence. I hand-labelled 30 claims and report agreement and Cohen's kappa (README). 30 is a small sample; it shows rough agreement, not a precise error rate.

17. **Why are the evals reproducible if the model is not deterministic?**
    Every request is cached by a hash of its full input. A re-run replays the stored responses. The CI gate uses the same cache, so it is free and stable.

18. **What does the CI gate do?**
    It runs WhyBot on 20 dev scenarios from the committed cache, then `bench/gate.py` compares accuracy@1 and citation precision with `bench/gate_baseline.json`. A drop of more than 5 points, or any crashed scenario, fails the build.

19. **What are latency and cost per question, and where do they go?**
    See README (p50, p95, USD per query). Each `Step` stores its own latency, tokens and cost, so the trace shows where time goes. Most of it is LLM calls; the tools take milliseconds.

20. **What would you do with more time?**
    Real text for documents, a larger test set with confidence intervals, prompt caching, a trained injection classifier, and partial streaming of the answer. Also in the README under "What I would change".

## 11. Things to be ready to admit

- The benchmark turned out too easy for the full system (dev accuracy at the ceiling). So the ablations do not show that the reranker, BM25 or dense search matters end to end. Say this before the interviewer finds it.
- Every system scored 100% on injection resistance, even the baselines. The model resisted by itself. My code defences are unit-tested, but the benchmark does not prove they were needed.
- LLM-only beat plain RAG on accuracy@1 because it always guesses and RAG abstains. Explain why that is not a win for LLM-only (0% faithfulness, wrong on every unanswerable question).
- The verifier wrongly dropped correct causes: two in the first dev run, one on test. I changed its prompt once after the dev run. That is tuning on dev, and it is written down (`results/dev_v0`).
- Three test ablation rows are missing because the API key hit its usage limit mid-run.

- I wrote the benchmark and the system. That is a bias risk. The time split, the frozen test run and the decoy, unanswerable and subtle-injection cases are how I reduce it.
- Accuracy is strict (type and segment). `results/*/metrics.json` also has `type_accuracy_at_1`, which is looser.
- The baselines are simple on purpose. Plain RAG has no date filter. A stronger RAG baseline would close some of the gap.
- If a number in the README looks bad, it stays. The rule of this project is that every figure comes from a committed run.
