# Decisions

- 2026-10-20: Core domain (rules, evaluator, status derivation) uses stdlib dataclasses so it is dependency-free and unit-testable anywhere. Pydantic is introduced only at the API boundary.
- 2026-10-20: Untrusted rules (unverified, conflicting, expired, not yet effective, or source not re-checked within 30 days) always evaluate to `unknown`, never `met` or `not_met`.
- 2026-10-20: `potential_match` requires every condition `met` AND a confirmed open application window; otherwise `application_status_unconfirmed`. `closed` requires explicit closure evidence.
- 2026-10-20: Development may use an alternative OpenAI-compatible endpoint (config only). Final demo and submission must run on Nebius Token Factory. Nebius access is currently pending.
- 2026-10-20: Opportunity = (program, institution) in the long run; income caps and deadlines are institution-level for HEC NBS. The seed catalog currently holds national-level program records only.
- 2026-10-20: Conditions that cannot be checked from the profile (committee-assessed need, partner-university lists, exclusion lists) are stored as `unevaluable` and always appear in the ledger as `unknown`, so a program can never reach `potential_match` while they are open.
- 2026-10-20: A `verified` rule may cite only tier A/B sources (enforced by the catalog loader). Tier C (blogs, aggregators, news) is lead-only.
- 2026-10-20: PEEF income limit stored `unverified` because the only official page is undated, has unmodeled exemptions, and secondary sites disagree.
- 2026-10-20: Added `any_of` (60% marks OR CGPA 2.5), `ne`, boolean `eq`, and per-rule `ambiguity` to the engine.
- 2026-10-21: The model never decides statuses. It extracts profile fields (all output re-validated by normalize_profile) and rephrases ledger facts. Explanations are rejected and replaced by a visibly labelled template if they contain promises, links, numbers not in the facts, or unknown rule ids.
- 2026-10-21: One model call per chat turn (extraction). Clarifying questions are deterministic templates (English and Urdu) restricted to fields the catalog's rules use. Urdu strings need review by a native speaker before the demo.
- 2026-10-21: No live-model endpoint is faked: without a configured client `/api/assistant/message` returns 503 and `/narrative` returns a template labelled `generated_by: template`.
