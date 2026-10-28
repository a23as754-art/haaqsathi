"""Assemble the Eligibility Evidence Ledger for one (profile, program) pair."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .reasons import REASONS
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
            reason=REASONS["unevaluable"]["en"],
            source_document_id=u.source_id, source_url=u.source_url, source_passage=u.passage,
            source_published=u.source_published, source_last_checked=u.source_last_checked,
            ambiguity=u.ambiguity, missing_fields=(), next_action=u.next_action, reason_code="unevaluable",
            requirement_ur=u.description_ur, ambiguity_ur=u.ambiguity_ur, next_action_ur=u.next_action_ur))
    status = derive_opportunity_status(results, program.application_confirmed_open, program.closure_evidenced)
    return Ledger(program.id, status, tuple(results))
