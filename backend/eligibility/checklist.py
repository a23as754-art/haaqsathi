"""Deterministic application-readiness checklist built from a ledger (tool 4: build_action_plan)."""
from __future__ import annotations

from dataclasses import dataclass

from .models import ConditionStatus as C, OpportunityStatus as O

FIELD_LABELS = {
    "en": {
        "education_level": "education level", "province": "province of residence",
        "domicile_province": "domicile province", "institution": "institution",
        "institution_sector": "institution type (public or private)",
        "admission_basis": "admission type (merit or self-finance)", "intended_degree": "intended degree",
        "marks_percent": "marks percentage", "cgpa": "CGPA",
        "monthly_family_income_pkr": "family monthly income", "receives_other_scholarship": "other scholarship status",
    },
    "ur": {
        "education_level": "تعلیمی سطح", "province": "رہائشی صوبہ", "domicile_province": "ڈومیسائل کا صوبہ",
        "institution": "ادارے کا نام", "institution_sector": "یونیورسٹی کی قسم (سرکاری یا نجی)",
        "admission_basis": "داخلے کی قسم (میرٹ یا سیلف فنانس)", "intended_degree": "ڈگری",
        "marks_percent": "فیصد نمبر", "cgpa": "سی جی پی اے", "monthly_family_income_pkr": "گھر کی ماہانہ آمدنی",
        "receives_other_scholarship": "دوسرے وظیفے کی صورتحال",
    },
}
TEXT = {
    "en": {
        "provide": 'Add your {labels} so that "{req}" can be checked.',
        "review": "Likely not eligible on this point: {req}. {action}",
        "window": "Confirm the current application window and deadline with the official source or your university.",
        "apply": "How to apply: {note}",
    },
    "ur": {
        "provide": 'اپنی {labels} شامل کریں تاکہ "{req}" کی جانچ ہو سکے۔',
        "review": "اس نکتے پر غالباً اہل نہیں: {req}۔ {action}",
        "window": "سرکاری ماخذ یا اپنی یونیورسٹی سے درخواست کی موجودہ مدت اور آخری تاریخ کی تصدیق کریں۔",
        "apply": "درخواست کیسے دیں: {note}",
    },
}
_ORDER = {"provide_info": 0, "verify": 1, "review": 2, "apply": 3}


@dataclass(frozen=True)
class ChecklistItem:
    kind: str            # provide_info | verify | review | apply
    text: str
    rule_id: str | None = None
    source_url: str | None = None


def build_action_plan(program, ledger, language: str = "en") -> list[ChecklistItem]:
    from backend.services.localize import localize_entry   # local import: services depend on eligibility
    lang = "ur" if language == "ur" else "en"
    tx, labels = TEXT[lang], FIELD_LABELS[lang]
    items: list[ChecklistItem] = []
    for e in ledger.entries:
        loc = localize_entry(e, lang)
        if e.status == C.UNKNOWN and e.missing_fields:
            names = ("، " if lang == "ur" else ", ").join(labels.get(f, f) for f in e.missing_fields)
            items.append(ChecklistItem("provide_info", tx["provide"].format(labels=names, req=loc["requirement"]),
                                       e.rule_id, e.source_url))
        elif e.status == C.UNKNOWN:
            items.append(ChecklistItem("verify", loc["next_action"], e.rule_id, e.source_url))
        elif e.status == C.NOT_MET:
            items.append(ChecklistItem("review", tx["review"].format(req=loc["requirement"], action=loc["next_action"]),
                                       e.rule_id, e.source_url))

    if not program.application_confirmed_open and ledger.status != O.CLOSED:
        items.append(ChecklistItem("verify", tx["window"], None, program.application_url))
    note = program.application_note_ur if lang == "ur" and program.application_note_ur else program.application_note
    if ledger.status not in (O.LIKELY_NOT_ELIGIBLE, O.CLOSED) and note:
        items.append(ChecklistItem("apply", tx["apply"].format(note=note), None, program.application_url))

    seen, out = set(), []
    for it in sorted(items, key=lambda i: _ORDER[i.kind]):   # stable: keeps ledger order inside a kind
        if it.text not in seen:
            seen.add(it.text)
            out.append(it)
    return out
