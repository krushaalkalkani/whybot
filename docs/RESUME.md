# Resume bullets

These three bullets are filled by `scripts/readme_results.py` from `results/summary.json`. Do not edit the numbers by hand. If a value says "not run yet", do not use that bullet yet.

<!-- results:start -->
1. Built WhyBot, a root-cause analysis agent (plain-Python state machine on the Claude API, no framework) with 4 typed tools over Postgres + pgvector; reached **97.5%** root-cause accuracy@1 on a held-out 40-scenario test split vs **30.0%** for vector RAG and **37.5%** for LLM-only, at **$0.0038** per query (p50 latency **17.9 s**).

2. Designed a seeded synthetic benchmark (80 scenarios, 6 cause types, 12 decoys, 8 unanswerable, 8 prompt-injection) and an eval harness with ablations and an LLM judge (**not run yet** agreement with 30 hand labels); a CI gate fails the build if accuracy@1 or citation precision drops by more than 5 points.

3. Added hybrid retrieval (BM25 + ONNX bge-small + RRF + cross-encoder), a citation verifier and abstain rules: **100.0%** citation precision, **97.5%** abstention accuracy, **100.0%** prompt-injection resistance; **34 of 34** security test cases (OWASP LLM Top 10) pass.
<!-- results:end -->

Rules for using them:

- Quote numbers exactly as they appear here.
- Say "synthetic benchmark" when you talk about the scores.
- The test split has 40 scenarios. Do not describe small gaps as significant.
