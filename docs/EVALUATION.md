# Evaluation

Run: `python -m backend.evaluation.run --mode scripted --strict`  (report: `reports/benchmark-scripted.md` and `.json`)
Live model run (needs `NEBIUS_API_KEY`, `NEBIUS_MODEL`): `python -m backend.evaluation.run --mode live`

## What it measures
60 synthetic cases in `data/fixtures/benchmark.json`: 32 eligibility (straightforward, ineligible, missing or ambiguous,
outdated or conflicting sources), 4 Urdu ledger rendering, 12 extraction (6 English, 6 Urdu, 2 injection attempts),
12 explanation-guard cases (promises, invented numbers, links, unknown ids, obeyed injection, model failure).
Expected results were written by hand from the source rules, never by running the engine.

## Modes
- **scripted**: model replies come from the benchmark file. Measures our deterministic code and validation layers only.
- **live**: calls the real model for extraction and explanations. Only this mode can say anything about model quality, Urdu understanding, latency or cost. **Not yet run** (no Nebius access so far).

## Latest result (scripted, 2026-10-22)
60/60 cases passed; rule accuracy 1.000 (94 checks), unknown handling 1.000 (35), citation validity 1.000 (216 entries),
false not_met 0, unsupported claims 0, extraction leaks 0. See `reports/benchmark-scripted.md`.

## How to read this honestly
- A perfect score means the engine matches the author's own expectations, not that the rules are right. Rule correctness depends on the sources, which are documented in `SOURCE_VALIDATION.md` and are partly undated.
- The runner is tested to fail: `tests/unit/test_evaluation.py` flips expectations and checks that the benchmark notices.
- Not measured: live model latency and cost, Urdu understanding by a real model, retrieval recall (no retrieval layer exists), end-to-end browser success.
- Targets from the project brief (95% accuracy and citations, 0 unsupported claims, 95% unknown handling, 90% Urdu relative to English) are engineering targets. Only the Urdu-relative one needs the live model.
