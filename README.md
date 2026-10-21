# HaqSaathi (work in progress)

Bilingual (Urdu/English) scholarship discovery and application-readiness assistant for students in Pakistan.
Central feature: an **Eligibility Evidence Ledger**. Every condition is `met`, `not_met` or `unknown`, with the
official source passage, URL and the date it was last checked. Eligibility is decided by deterministic code, never by the LLM.
This is an information assistant, not an official HEC, PEEF or university service, and it never guarantees funding.

## Status (honest)
- Done and tested: eligibility engine, catalog loader, ledger, checklist, search ranking, profile validation (116 passing unit tests; 13 API tests skipped until fastapi/httpx are installed).
- Done and tested with a fake model client: profile extraction (Urdu/English), clarifying questions, ledger explanation with output validation and labelled template fallback.
- Written but not yet run: FastAPI wiring (`backend/api/app.py`) and its tests; run them locally (below).
- Not done: any live Nebius/NVIDIA model call (pending account access; the agent code has only been exercised against a test double), Urdu/English UI, database, deployment, benchmark, license, demo.
- Catalog: 2 programs (HEC Need Based, PEEF Master Level). No deadline or open window is asserted. See `docs/SOURCE_VALIDATION.md`.

## Run
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    python3 -m unittest discover -s tests -t . -v      # or: pytest
    uvicorn backend.api.app:app --reload               # http://127.0.0.1:8000/docs

## Model provider (development)
Copy `.env.example` to `.env`. `scripts/smoke_nebius.py` makes one live call. The final demo must run on Nebius Token Factory with an NVIDIA open model.
