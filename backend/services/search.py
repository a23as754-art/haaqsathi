"""Rank catalog programs for a profile using transparent, non-numeric criteria.

Order: status (potential_match, application_status_unconfirmed, needs_verification,
likely_not_eligible, closed), then more conditions met, then fewer unknown, then name.
No match percentage or funding probability is computed or exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.eligibility.engine import DEFAULT_MAX_SOURCE_AGE_DAYS
from backend.eligibility.ledger import Ledger, build_ledger
from backend.eligibility.models import ConditionStatus as C, OpportunityStatus as O, StudentProfile

STATUS_ORDER = {O.POTENTIAL_MATCH: 0, O.APPLICATION_STATUS_UNCONFIRMED: 1, O.NEEDS_VERIFICATION: 2,
                O.LIKELY_NOT_ELIGIBLE: 3, O.CLOSED: 4}


@dataclass(frozen=True)
class SearchResult:
    program: object
    ledger: Ledger
    counts: dict


def search_opportunities(catalog, profile: StudentProfile, today: date,
                         max_source_age_days: int = DEFAULT_MAX_SOURCE_AGE_DAYS) -> list[SearchResult]:
    out = []
    for p in catalog.programs:
        led = build_ledger(p, profile, today, max_source_age_days)
        counts = {s.value: sum(1 for e in led.entries if e.status == s) for s in C}
        out.append(SearchResult(p, led, counts))
    out.sort(key=lambda r: (STATUS_ORDER[r.ledger.status], -r.counts["met"], r.counts["unknown"], r.program.name))
    return out
