"""Deterministic eligibility evaluation. The LLM never decides a status; it only explains these results."""
from __future__ import annotations

from datetime import date

from .reasons import CONFLICT_AMBIGUITY, REASONS
from .models import (ConditionStatus as C, OpportunityStatus as O, EvaluationResult,
                     Rule, StudentProfile, is_number)

DEFAULT_MAX_SOURCE_AGE_DAYS = 30
_NUMERIC = ("gte", "lte", "between")


def _norm(v):
    return v.strip().casefold() if isinstance(v, str) else v


def _present(v) -> bool:
    return not (v is None or (isinstance(v, str) and not v.strip()))


def _result(rule: Rule, status: C, code: str, pv, ambiguity=None, ambiguity_ur=None, missing=()):
    return EvaluationResult(
        rule_id=rule.id, rule_version=rule.version, status=status, requirement=rule.description,
        profile_value=pv, reason=REASONS[code]["en"], source_document_id=rule.source_document_id,
        source_url=rule.source_url, source_passage=rule.source_passage,
        source_published=rule.source_published, source_last_checked=rule.last_checked,
        ambiguity=ambiguity if ambiguity is not None else rule.ambiguity,
        missing_fields=tuple(missing), next_action=rule.next_action, reason_code=code,
        requirement_ur=rule.description_ur,
        ambiguity_ur=ambiguity_ur if ambiguity_ur is not None else rule.ambiguity_ur,
        next_action_ur=rule.next_action_ur)


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
    unk = lambda code, **kw: _result(rule, C.UNKNOWN, code, pv, **kw)

    # Source trust gates first: an untrusted rule can never produce met / not_met.
    if rule.verification == "conflicting":
        return unk("conflicting", ambiguity=rule.ambiguity or CONFLICT_AMBIGUITY["en"],
                   ambiguity_ur=rule.ambiguity_ur or (None if rule.ambiguity else CONFLICT_AMBIGUITY["ur"]))
    if rule.verification != "verified":
        return unk("unverified")
    if rule.effective_from and today < rule.effective_from:
        return unk("not_yet_effective")
    if rule.effective_until and today > rule.effective_until:
        return unk("expired")
    if rule.last_checked is None or (today - rule.last_checked).days > max_source_age_days:
        return unk("stale")

    # Data gates: missing or invalid profile data is never treated as satisfying a condition.
    if rule.op == "any_of":
        outs = [_check(profile, f, o, v) for f, o, v in rule.value]
        values = {f: pv_ for (f, _, _), (_, _, pv_) in zip(rule.value, outs)}
        if any(s == C.MET for s, _, _ in outs):
            return _result(rule, C.MET, "alt_met", values)
        if all(s == C.NOT_MET for s, _, _ in outs):
            return _result(rule, C.NOT_MET, "alt_failed", values)
        missing = tuple(dict.fromkeys(m for _, ms, _ in outs for m in ms))
        return _result(rule, C.UNKNOWN, "alt_unknown", values, missing=missing)

    status, missing, pv = _check(profile, rule.field, rule.op, rule.value)
    if status == C.UNKNOWN:
        return _result(rule, C.UNKNOWN, "missing_info" if not _present(pv) else "invalid_value", pv, missing=missing)
    return _result(rule, status, "satisfied" if status == C.MET else "not_satisfied", pv)


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
