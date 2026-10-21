"""Deterministic eligibility evaluation. The LLM never decides a status; it only explains these results."""
from __future__ import annotations

from datetime import date

from .models import (ConditionStatus as C, OpportunityStatus as O, EvaluationResult,
                     Rule, StudentProfile, is_number)

DEFAULT_MAX_SOURCE_AGE_DAYS = 30
_NUMERIC = ("gte", "lte", "between")


def _norm(v):
    return v.strip().casefold() if isinstance(v, str) else v


def _present(v) -> bool:
    return not (v is None or (isinstance(v, str) and not v.strip()))


def _result(rule: Rule, status: C, reason: str, pv, ambiguity=None, missing=()):
    return EvaluationResult(
        rule_id=rule.id, rule_version=rule.version, status=status, requirement=rule.description,
        profile_value=pv, reason=reason, source_document_id=rule.source_document_id,
        source_url=rule.source_url, source_passage=rule.source_passage,
        source_published=rule.source_published, source_last_checked=rule.last_checked,
        ambiguity=ambiguity if ambiguity is not None else rule.ambiguity,
        missing_fields=tuple(missing), next_action=rule.next_action)


def _check(profile: StudentProfile, field: str, op: str, rv):
    """Evaluate one simple condition. Returns (status, missing_fields, profile_value)."""
    pv = getattr(profile, field, None)
    if not _present(pv):
        return C.UNKNOWN, (field,), pv
    if op in _NUMERIC:
        if not is_number(pv):
            return C.UNKNOWN, (field,), pv
        ok = pv >= rv if op == "gte" else pv <= rv if op == "lte" else rv[0] <= pv <= rv[1]
    elif op == "in":
        ok = _norm(pv) in {_norm(x) for x in rv}
    elif op == "ne":
        ok = _norm(pv) != _norm(rv)
    else:
        ok = _norm(pv) == _norm(rv)
    return (C.MET if ok else C.NOT_MET), (), pv


def evaluate_rule(rule: Rule, profile: StudentProfile, today: date,
                  max_source_age_days: int = DEFAULT_MAX_SOURCE_AGE_DAYS) -> EvaluationResult:
    pv = None if rule.op == "any_of" else getattr(profile, rule.field, None)
    unk = lambda reason, **kw: _result(rule, C.UNKNOWN, reason, pv, **kw)

    # Source trust gates first: an untrusted rule can never produce met / not_met.
    if rule.verification == "conflicting":
        return unk("Sources conflict on this requirement.",
                   ambiguity=rule.ambiguity or "Conflicting information found in sources.")
    if rule.verification != "verified":
        return unk("This requirement has not been verified against an official source.")
    if rule.effective_from and today < rule.effective_from:
        return unk("This requirement version is not yet in effect.")
    if rule.effective_until and today > rule.effective_until:
        return unk("This requirement version has expired and needs re-checking.")
    if rule.last_checked is None or (today - rule.last_checked).days > max_source_age_days:
        return unk("The source has not been re-checked recently enough.")

    # Data gates: missing or invalid profile data is never treated as satisfying a condition.
    if rule.op == "any_of":
        outs = [_check(profile, f, o, v) for f, o, v in rule.value]
        values = {f: pv_ for (f, _, _), (_, _, pv_) in zip(rule.value, outs)}
        if any(s == C.MET for s, _, _ in outs):
            return _result(rule, C.MET, "At least one alternative requirement is satisfied.", values)
        if all(s == C.NOT_MET for s, _, _ in outs):
            return _result(rule, C.NOT_MET, "None of the alternative requirements is satisfied.", values)
        missing = tuple(dict.fromkeys(m for _, ms, _ in outs for m in ms))
        return _result(rule, C.UNKNOWN, "Not enough information to evaluate the alternatives.", values, missing=missing)

    status, missing, pv = _check(profile, rule.field, rule.op, rule.value)
    if status == C.UNKNOWN:
        why = ("Needed information is missing from the profile." if not _present(pv)
               else "The profile value is not valid for this requirement.")
        return _result(rule, C.UNKNOWN, why, pv, missing=missing)
    return _result(rule, status,
                   "Requirement is satisfied by the profile." if status == C.MET
                   else "Requirement is not satisfied by the profile.", pv)


def evaluate_all(rules, profile: StudentProfile, today: date,
                 max_source_age_days: int = DEFAULT_MAX_SOURCE_AGE_DAYS) -> list[EvaluationResult]:
    return [evaluate_rule(r, profile, today, max_source_age_days) for r in rules]


def derive_opportunity_status(results, application_confirmed_open: bool, closure_evidenced: bool) -> O:
    """Priority: evidenced closure > any verified not_met > any unknown > unconfirmed window > potential_match."""
    if closure_evidenced:
        return O.CLOSED
    statuses = [r.status for r in results]
    if C.NOT_MET in statuses:
        return O.LIKELY_NOT_ELIGIBLE
    if not statuses or C.UNKNOWN in statuses:
        return O.NEEDS_VERIFICATION
    return O.POTENTIAL_MATCH if application_confirmed_open else O.APPLICATION_STATUS_UNCONFIRMED
