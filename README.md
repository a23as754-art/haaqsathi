# HaqSaathi (work in progress)

Bilingual (Urdu/English) scholarship discovery and application-readiness assistant for students in Pakistan.
Central feature: an **Eligibility Evidence Ledger**. Every condition is `met`, `not_met` or `unknown`, with the
official source passage, URL and the date it was last checked. Eligibility is decided by deterministic code, never by the LLM.
This is an information assistant, not an official HEC, PEEF or university service, and it never guarantees funding.

## Status (honest)
- Benchmark: 60 synthetic cases, scripted mode 60/60 (see `docs/EVALUATION.md`; live-model mode not yet run).
- Tested locally: eligibility engine, catalog loader, ledger, checklist, search ranking, profile validation, API and localization coverage (172 Python tests passed; 1 Starlette/httpx deprecation warning).
- Done and tested with a fake model client: profile extraction (Urdu/English), clarifying questions, ledger explanation with output validation and labelled template fallback.
- API and web functionality have automated test coverage. Latest reported local results: 172 Python tests passed and 11 web tests passed.
- Not yet verified or complete: live Nebius/NVIDIA model call; production database and deployment; license review; final demo readiness; native-speaker review of Urdu wording; real-browser and mobile checks.
- Catalog: 2 programs (HEC Need Based, PEEF Master Level). No deadline or open window is asserted. See `docs/SOURCE_VALIDATION.md`.

## Web app
`web/` is a build-free static app (vanilla JS, Urdu RTL, no external requests, strict CSP) served by FastAPI at `/`.
Chosen over a separate Next.js service for a solo, one-process deployment. Checklist and condition text are available in Urdu
(catalog `*_ur` fields). Known gaps: Urdu strings are machine-drafted and need native review; not yet checked in a real browser or on a phone.

## Run
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    python3 -m unittest discover -s tests -t . -v      # or: pytest
    python -m backend.evaluation.run --strict          # 60-case benchmark -> reports/benchmark-scripted.md
    npm run test:web                                   # JS logic tests (Node 18+), no install needed
    uvicorn backend.api.app:app --reload  # http://127.0.0.1:8000/docs


## Model provider status
Live model integration is currently unverified and paused. The application must remain usable in clearly labelled no-model or template-fallback mode. Eligibility decisions are made by deterministic code, never by the language model. A live provider will be selected and tested before a model-powered demo is claimed. Never commit `.env` or API credentials.
