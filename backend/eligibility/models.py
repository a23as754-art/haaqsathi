"""Domain types for the Eligibility Evidence Ledger (stdlib only; Pydantic comes at the API edge)."""
from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import date
from enum import Enum


class ConditionStatus(str, Enum):
    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"


class OpportunityStatus(str, Enum):
    POTENTIAL_MATCH = "potential_match"
    NEEDS_VERIFICATION = "needs_verification"
    LIKELY_NOT_ELIGIBLE = "likely_not_eligible"
    APPLICATION_STATUS_UNCONFIRMED = "application_status_unconfirmed"
    CLOSED = "closed"


@dataclass(frozen=True)
class StudentProfile:
    """Minimal MVP profile. No identity numbers, no documents, no banking data.

    Vocabulary (keep stable; the UI maps labels to these values):
      education_level: matric | intermediate | undergraduate | masters | mphil | phd
      institution_sector: public | private
      admission_basis: open_merit | self_finance | other
    """
    education_level: str | None = None
    province: str | None = None                  # province of residence
    domicile_province: str | None = None         # domicile is not the same as residence
    institution: str | None = None
    institution_sector: str | None = None
    admission_basis: str | None = None
    intended_degree: str | None = None
    marks_percent: float | None = None
    cgpa: float | None = None
    monthly_family_income_pkr: float | None = None
    receives_other_scholarship: bool | None = None


PROFILE_FIELDS = frozenset(f.name for f in fields(StudentProfile))
SIMPLE_OPS = frozenset({"eq", "ne", "in", "gte", "lte", "between"})
OPS = SIMPLE_OPS | {"any_of"}
VERIFICATION = frozenset({"verified", "unverified", "conflicting"})


def is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def validate_condition(field: str, op: str, value) -> None:
    if field not in PROFILE_FIELDS:
        raise ValueError(f"unknown profile field: {field}")
    if op not in SIMPLE_OPS:
        raise ValueError(f"unknown operator: {op}")
    if op in ("gte", "lte") and not is_number(value):
        raise ValueError(f"{op} needs a numeric value")
    if op == "between":
        if not (isinstance(value, (tuple, list)) and len(value) == 2 and all(is_number(x) for x in value) and value[0] <= value[1]):
            raise ValueError("between needs an ordered numeric pair")
    if op == "in" and not (isinstance(value, (tuple, list, frozenset, set)) and len(value) > 0):
        raise ValueError("in needs a non-empty collection")
    if op in ("eq", "ne") and isinstance(value, (tuple, list, dict, set, frozenset)):
        raise ValueError(f"{op} needs a scalar value")


@dataclass(frozen=True)
class Rule:
    """One eligibility condition. For op='any_of', field must be '*' and value is a tuple of
    (field, op, value) branches; the rule is met if any branch is met."""
    id: str
    field: str
    op: str
    value: object
    description: str
    verification: str = "unverified"
    source_document_id: str | None = None
    source_url: str | None = None
    source_passage: str | None = None
    source_published: date | None = None
    last_checked: date | None = None
    version: str = "1"
    effective_from: date | None = None
    effective_until: date | None = None
    next_action: str = "Check the official source for the current requirement."
    ambiguity: str | None = None
    description_ur: str | None = None
    ambiguity_ur: str | None = None
    next_action_ur: str | None = None

    def __post_init__(self):
        if self.verification not in VERIFICATION:
            raise ValueError(f"bad verification value: {self.verification}")
        if self.op == "any_of":
            if self.field != "*":
                raise ValueError("any_of rules must use field '*'")
            v = self.value
            if not (isinstance(v, (tuple, list)) and len(v) >= 2):
                raise ValueError("any_of needs at least two branches")
            for b in v:
                if not (isinstance(b, (tuple, list)) and len(b) == 3):
                    raise ValueError("each any_of branch must be (field, op, value)")
                validate_condition(*b)
        else:
            validate_condition(self.field, self.op, self.value)


@dataclass(frozen=True)
class EvaluationResult:
    rule_id: str
    rule_version: str
    status: ConditionStatus
    requirement: str
    profile_value: object
    reason: str
    source_document_id: str | None
    source_url: str | None
    source_passage: str | None
    source_published: date | None
    source_last_checked: date | None
    ambiguity: str | None
    missing_fields: tuple
    next_action: str
    reason_code: str = ""
    requirement_ur: str | None = None
    ambiguity_ur: str | None = None
    next_action_ur: str | None = None
