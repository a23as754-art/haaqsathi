"""Assemble the Eligibility Evidence Ledger for one (profile, program) pair."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .engine import DEFAULT_MAX_SOURCE_AGE_DAYS, derive_opportunity_status, evaluate_all
from .models import ConditionStatus as C, EvaluationResult, OpportunityStatus, StudentProfile


@dataclass(frozen=True)
class Ledger:
    program_id: str
    status: OpportunityStatus
    entries: tuple


def build_ledger(program, profile: StudentProfile, today: date,
                 max_source_age_days: int = DEFAULT_MAX_SOURCE_AGE_DAYS) -> Ledger:
    results = list(evaluate_all(program.rules, profile, today, max_source_age_days))
    for u in program.unevaluable:
        results.append(EvaluationResult(
            rule_id=u.id, rule_version="1", status=C.UNKNOWN, requirement=u.description, profile_value=None,
            reason="This condition cannot be checked automatically from the profile.",
            source_document_id=u.source_id, source_url=u.source_url, source_passage=u.passage,
            source_published=u.source_published, source_last_checked=u.source_last_checked,
            ambiguity=u.ambiguity, missing_fields=(), next_action=u.next_action))
    status = derive_opportunity_status(results, program.application_confirmed_open, program.closure_evidenced)
    return Ledger(program.id, status, tuple(results))
