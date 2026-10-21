"""FastAPI wiring over the pure-Python services. Run: uvicorn backend.api.app:app --reload"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.agents.explain import explain_ledger
from backend.agents.orchestrator import handle_message
from backend.catalog.loader import Catalog, load_catalog
from backend.eligibility.checklist import build_action_plan
from backend.eligibility.ledger import build_ledger
from backend.eligibility.models import PROFILE_FIELDS
from backend.models.nebius import ModelError, NebiusClient
from backend.services.profile import normalize_profile
from backend.services.search import search_opportunities
from backend.services.serialize import to_jsonable
from backend.services.sources import describe_source

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "catalog.json"
DISCLAIMER = ("HaqSaathi is an information and preparation assistant, not an official HEC, PEEF or university "
              "service. Potential eligibility is not an award decision and nothing here guarantees funding.")


class ProfileIn(BaseModel):
    """Extra keys are accepted here on purpose so the normalizer can reject them with a clear,
    value-free message (e.g. identity numbers are refused, never stored or echoed)."""
    model_config = ConfigDict(extra="allow")
    education_level: str | None = None
    province: str | None = None
    domicile_province: str | None = None
    institution: str | None = None
    institution_sector: str | None = None
    admission_basis: str | None = None
    intended_degree: str | None = None
    marks_percent: float | str | None = None
    cgpa: float | str | None = None
    monthly_family_income_pkr: float | str | None = None
    receives_other_scholarship: bool | None = None


class ProfileBody(BaseModel):
    profile: ProfileIn


class MessageBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str | None = None


class NarrativeBody(BaseModel):
    profile: ProfileIn
    language: str | None = None


class ChecklistBody(BaseModel):
    profile: ProfileIn
    program_id: str


def _env_client():
    if not os.environ.get("NEBIUS_API_KEY"):
        return None
    try:
        return NebiusClient()
    except ModelError:
        return None


def create_app(catalog: Catalog | None = None, today_fn: Callable[[], date] = date.today,
               model_client=None) -> FastAPI:
    cat = catalog or load_catalog(os.environ.get("HAQSAATHI_CATALOG", DEFAULT_CATALOG))
    client = model_client or _env_client()   # None => no live model; endpoints say so, nothing is faked
    app = FastAPI(title="HaqSaathi API", version="0.1.0")

    def profile_from(p: ProfileIn):
        profile, errors = normalize_profile(p.model_dump(exclude_none=True))
        if errors:
            raise HTTPException(status_code=422, detail={"errors": errors})
        return profile

    def program_or_404(pid: str):
        try:
            return cat.program(pid)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown program.") from None

    def row(r):
        return {"program_id": r.program.id, "name": r.program.name, "organization": r.program.organization,
                "level": r.program.level, "status": r.ledger.status.value, "condition_counts": r.counts,
                "application": {"confirmed_open": r.program.application_confirmed_open,
                                "deadline": to_jsonable(r.program.application_deadline),
                                "note": r.program.application_note}}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "catalog_programs": len(cat.programs)}

    @app.post("/api/profile")
    def profile(body: ProfileBody):
        pr = profile_from(body.profile)
        return {"profile": to_jsonable(pr),
                "missing_fields": sorted(f for f in PROFILE_FIELDS if getattr(pr, f) is None)}

    @app.post("/api/opportunities/search")
    def search(body: ProfileBody):
        today = today_fn()
        results = search_opportunities(cat, profile_from(body.profile), today)
        return {"disclaimer": DISCLAIMER, "results": [row(r) for r in results]}

    @app.post("/api/matches/{program_id}/explain")
    def explain(program_id: str, body: ProfileBody):
        prog = program_or_404(program_id)
        led = build_ledger(prog, profile_from(body.profile), today_fn())
        return {"disclaimer": DISCLAIMER, "program": {"id": prog.id, "name": prog.name, "organization": prog.organization},
                "status": led.status.value, "entries": to_jsonable(led.entries)}

    @app.post("/api/matches/{program_id}/narrative")
    def narrative(program_id: str, body: NarrativeBody):
        prog = program_or_404(program_id)
        led = build_ledger(prog, profile_from(body.profile), today_fn())
        ex = explain_ledger(client, prog, led, body.language or "en")
        return {"disclaimer": DISCLAIMER, "status": ex.status, "generated_by": ex.generated_by,
                "fallback_reason": ex.fallback_reason, "summary": ex.summary,
                "items": [{"rule_id": rid, "text": t} for rid, t in ex.items]}

    @app.post("/api/assistant/message")
    def assistant(body: MessageBody):
        if client is None:
            raise HTTPException(status_code=503, detail="Model provider is not configured.")
        try:
            turn = handle_message(client, cat, body.message, today_fn(), body.language)
        except ModelError:
            raise HTTPException(status_code=502, detail="The model request failed. Please try again.") from None
        return {"disclaimer": DISCLAIMER, "language": turn.language, "profile": to_jsonable(turn.profile),
                "warnings": turn.warnings, "questions": turn.questions, "results": [row(r) for r in turn.results]}

    @app.post("/api/checklists/generate")
    def checklist(body: ChecklistBody):
        prog = program_or_404(body.program_id)
        led = build_ledger(prog, profile_from(body.profile), today_fn())
        return {"disclaimer": DISCLAIMER, "program_id": prog.id, "status": led.status.value,
                "items": to_jsonable(build_action_plan(prog, led))}

    @app.get("/api/sources/{source_id}")
    def source(source_id: str):
        s = cat.sources.get(source_id)
        if s is None:
            raise HTTPException(status_code=404, detail="Unknown source.")
        return describe_source(s, today_fn())

    return app


app = create_app()
