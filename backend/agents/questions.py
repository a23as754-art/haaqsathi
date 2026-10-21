"""Deterministic clarifying questions: ask only for fields the catalog's rules actually use."""
from __future__ import annotations

from dataclasses import fields as dc_fields

from backend.eligibility.models import StudentProfile

QUESTIONS = {
    "education_level": {"en": "What is your current education level (matric, intermediate, undergraduate, masters, MPhil, PhD)?",
                        "ur": "آپ کس تعلیمی سطح میں ہیں؟ (میٹرک، انٹرمیڈیٹ، انڈرگریجویٹ، ماسٹرز، ایم فل، پی ایچ ڈی)"},
    "province": {"en": "Which province do you live in?", "ur": "آپ کس صوبے میں رہتے ہیں؟"},
    "domicile_province": {"en": "Which province is your domicile from?", "ur": "آپ کا ڈومیسائل کس صوبے کا ہے؟"},
    "institution": {"en": "What is the name of your university or institution?", "ur": "آپ کی یونیورسٹی یا ادارے کا نام کیا ہے؟"},
    "institution_sector": {"en": "Is your university public or private?", "ur": "آپ کی یونیورسٹی سرکاری ہے یا نجی؟"},
    "admission_basis": {"en": "Were you admitted on open merit or on a self-finance basis?",
                        "ur": "آپ کا داخلہ اوپن میرٹ پر ہوا ہے یا سیلف فنانس پر؟"},
    "intended_degree": {"en": "Which degree are you studying or planning?", "ur": "آپ کون سی ڈگری کر رہے ہیں یا کرنا چاہتے ہیں؟"},
    "marks_percent": {"en": "What percentage did you score in your last qualifying exam?",
                      "ur": "پچھلے امتحان میں آپ کے فیصد نمبر کتنے تھے؟"},
    "cgpa": {"en": "What is your CGPA, if your degree uses one?", "ur": "آپ کا سی جی پی اے کتنا ہے؟"},
    "monthly_family_income_pkr": {"en": "Roughly what is your parents' total monthly income, in rupees?",
                                  "ur": "آپ کے والدین کی ماہانہ آمدنی تقریباً کتنی ہے (روپے میں)؟"},
    "receives_other_scholarship": {"en": "Are you currently receiving any other educational scholarship?",
                                   "ur": "کیا آپ اس وقت کوئی اور تعلیمی وظیفہ لے رہے ہیں؟"},
}
_ORDER = {f.name: i for i, f in enumerate(dc_fields(StudentProfile))}   # declaration order, deterministic


def _rule_fields(rule):
    return [b[0] for b in rule.value] if rule.op == "any_of" else [rule.field]


def next_questions(catalog, profile, language: str = "en", limit: int = 3) -> list[dict]:
    lang = "ur" if language == "ur" else "en"
    counts: dict[str, int] = {}
    for p in catalog.programs:
        for r in p.rules:
            for f in _rule_fields(r):
                if getattr(profile, f, None) is None:
                    counts[f] = counts.get(f, 0) + 1
    fields = sorted(counts, key=lambda f: (-counts[f], _ORDER.get(f, 99)))
    return [{"field": f, "text": QUESTIONS[f][lang]} for f in fields if f in QUESTIONS][:limit]
