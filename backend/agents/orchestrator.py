"""Bounded orchestration for one chat turn: exactly one model call (extraction), then deterministic tools."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.agents.extract import extract_profile
from backend.agents.questions import next_questions
from backend.eligibility.models import StudentProfile
from backend.services.search import search_opportunities
from backend.services.text import detect_language


@dataclass(frozen=True)
class TurnResult:
    language: str
    profile: StudentProfile
    warnings: list
    results: list
    questions: list


def handle_message(client, catalog, text: str, today: date, language: str | None = None) -> TurnResult:
    lang = language if language in ("en", "ur") else detect_language(text or "")
    ext = extract_profile(client, text)                       # the only model call this turn
    results = search_opportunities(catalog, ext.profile, today)
    return TurnResult(lang, ext.profile, ext.warnings, results, next_questions(catalog, ext.profile, lang))
