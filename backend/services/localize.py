from __future__ import annotations

from backend.eligibility.reasons import REASONS


def localize_entry(e, lang: str) -> dict:
    """Language-specific display text for one ledger entry. Falls back to English per field when Urdu
    is missing, and says which language the requirement text actually is in."""
    ur = lang == "ur"
    pick = lambda en, alt: alt if (ur and alt) else en
    reason = REASONS.get(e.reason_code, {}).get("ur" if ur else "en") or e.reason
    return {
        "requirement": pick(e.requirement, e.requirement_ur),
        "reason": reason,
        "ambiguity": pick(e.ambiguity, e.ambiguity_ur) if e.ambiguity else None,
        "next_action": pick(e.next_action, e.next_action_ur),
        "language": "ur" if ur and e.requirement_ur else "en",
    }
