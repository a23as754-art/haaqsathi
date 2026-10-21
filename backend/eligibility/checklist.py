"""Deterministic application-readiness checklist built from a ledger (tool 4: build_action_plan)."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ConditionStatus as C, OpportunityStatus as O

FIELD_LABELS = {
    "education_level": "education level", "province": "province of residence",
    "domicile_province": "domicile province", "institution": "institution",
    "institution_sector": "institution type (public or private)",
    "admission_basis": "admission type (merit or self-finance)", "intended_degree": "intended degree",
    "marks_percent": "marks percentage", "cgpa": "CGPA",
    "monthly_family_income_pkr": "family monthly income",
    "receives_other_scholarship": "other scholarship status",
}
_ORDER = {"provide_info": 0, "verify": 1, "review": 2, "apply": 3}


@dataclass(frozen=True)
class ChecklistItem:
    kind: str            # provide_info | verify | review | apply
    text: str
    rule_id: str | None = None
    source_url: str | None = None


def build_action_plan(program, ledger) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []
    for e in ledger.entries:
        if e.status == C.UNKNOWN and e.missing_fields:
            labels = ", ".join(FIELD_LABELS.get(f, f) for f in e.missing_fields)
            items.append(ChecklistItem("provide_info", f"Add your {labels} so that \"{e.requirement}\" can be checked.",
                                       e.rule_id, e.source_url))
        elif e.status == C.UNKNOWN:
            items.append(ChecklistItem("verify", e.next_action, e.rule_id, e.source_url))
        elif e.status == C.NOT_MET:
            items.append(ChecklistItem("review", f"Likely not eligible on this point: {e.requirement}. {e.next_action}",
                                       e.rule_id, e.source_url))

    if not program.application_confirmed_open and ledger.status != O.CLOSED:
        items.append(ChecklistItem(
            "verify", "Confirm the current application window and deadline with the official source or your university.",
            None, program.application_url))
    if ledger.status not in (O.LIKELY_NOT_ELIGIBLE, O.CLOSED) and program.application_note:
        items.append(ChecklistItem("apply", f"How to apply: {program.application_note}", None, program.application_url))

    seen, out = set(), []
    for it in sorted(items, key=lambda i: _ORDER[i.kind]):   # stable: keeps ledger order inside a kind
        if it.text not in seen:
            seen.add(it.text)
            out.append(it)
    return out
