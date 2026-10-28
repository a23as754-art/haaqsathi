# HaqSaathi — Project Plan

## 1. Product Goal

Build an Urdu/English scholarship discovery and application-readiness assistant for Pakistani students.

The system helps students understand scholarship requirements, identify missing information, review evidence, and prepare application checklists.

## 2. Non-Negotiable Eligibility Rules

- Eligibility decisions must be made by deterministic Python code, never by an LLM.
- Each requirement must have one status: `met`, `not_met`, or `unknown`.
- Every requirement should include official evidence, source URL, source date, ambiguity, and next action where available.
- Missing, stale, conflicting, ambiguous, or unverified evidence must not be treated as `met`.
- `potential_match` requires all mandatory conditions to be met and the application window to be confirmed open.
- `closed` requires explicit supporting evidence.
- Never invent requirements, deadlines, documents, benefits, or source URLs.
- Clearly label mock data and development-only model providers.

## 3. Current Baseline

Reported by the developer on the existing working copy:

- Python unit tests: 172 passed (latest local run).
- Scripted evaluation: 60 cases, no failures or missed targets.
- Web tests: 11 passed.
- `git diff --check`: no whitespace errors reported.

These are recorded developer-reported results; rerun them after relevant changes.

## 4. Workstreams

### A. Preserve and verify existing implementation

- Review the current Git diff before editing.
- Keep existing changes and untracked files intact.
- Run Python tests, web tests, and strict scripted evaluation.
- Do not reset, clean, stage, or commit without explicit approval.

### B. Scholarship source verification

- Verify HEC Need Based Scholarship requirements against official documents.
- Verify PEEF Master Level requirements and application-window information.
- Record source URLs, retrieval/verification dates, ambiguities, and unresolved questions.
- Do not present unverified scholarship details as confirmed facts.

### C. Eligibility evidence ledger

- Verify the status logic and evidence fields for every condition.
- Test missing, stale, conflicting, expired, and ambiguous evidence.
- Test numerical edge cases, including NaN and positive/negative infinity.
- Keep decision-making deterministic and auditable.

### D. Urdu/English experience

- Verify profile extraction and checklist localization in both languages.
- Keep extracted profile values separate from eligibility decisions.
- Ensure explanations accurately reflect the ledger and identify the next action.

### E. Model integration

- Keep local/test provider configuration separate from final deployment configuration.
- Test provider errors, missing credentials, malformed responses, and timeouts.
- Verify a real supported NVIDIA open-model call through Nebius Token Factory before claiming live integration.
- Never claim a mocked provider proves live model functionality.

### F. Security and deployment readiness

- Review prompt-injection handling for retrieved web pages.
- Preserve safe URL handling, Content Security Policy, and unsafe-DOM protections.
- Ensure secrets are not committed or written to logs.
- Document setup, configuration, tests, and known limitations.
- Confirm licensing and deployment requirements before release.

## 5. Definition of Done

A work item is complete only when:

1. Its acceptance criteria are documented.
2. Relevant automated tests pass.
3. Existing regression tests remain green.
4. Evidence and limitations are documented honestly.
5. Git diff is reviewed and contains only intended changes.
6. No unsupported eligibility or live-integration claims are introduced.

## 6. Immediate Next Steps

1. Inspect the current README, architecture, and Git diff.
2. Reconcile documentation with the actual implementation and tests.
3. Verify official scholarship sources and document unresolved gaps.
4. Select one small, testable implementation task.
5. Validate the change before moving to the next task.

## 7. Known Limitations to Recheck

- Live Nebius/NVIDIA model integration must be verified against the actual configured account and endpoint.
- Scholarship source verification may be incomplete.
- Deployment, licensing, and final demo readiness must not be assumed.
- Re-run all baseline tests rather than relying solely on historical output.
