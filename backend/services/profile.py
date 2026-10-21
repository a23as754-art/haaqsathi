"""Validate and normalize a student profile submitted by the UI or extracted by the model.

Privacy: identity numbers, credentials and banking details are refused outright and their
values are never echoed back or logged.
"""
from __future__ import annotations

import math

from backend.services.text import ascii_digits

from backend.eligibility.models import PROFILE_FIELDS, StudentProfile

VOCAB = {
    "education_level": {"matric", "intermediate", "undergraduate", "masters", "mphil", "phd"},
    "institution_sector": {"public", "private"},
    "admission_basis": {"open_merit", "self_finance", "other"},
}
PROVINCES = {
    "punjab": "Punjab", "sindh": "Sindh", "balochistan": "Balochistan",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa", "kpk": "Khyber Pakhtunkhwa", "kp": "Khyber Pakhtunkhwa",
    "islamabad capital territory": "Islamabad Capital Territory", "ict": "Islamabad Capital Territory",
    "islamabad": "Islamabad Capital Territory",
    "gilgit-baltistan": "Gilgit-Baltistan", "gb": "Gilgit-Baltistan",
    "azad jammu and kashmir": "Azad Jammu and Kashmir", "ajk": "Azad Jammu and Kashmir",
}
RANGES = {"marks_percent": (0, 100), "cgpa": (0, 4.0), "monthly_family_income_pkr": (0, 10_000_000)}
FORBIDDEN = {"cnic", "national_id", "id_number", "passport", "passport_number", "password",
             "bank_account", "iban", "card_number", "account_number", "date_of_birth", "phone", "email"}
MAX_TEXT = 200


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    elif isinstance(v, str):
        try:
            x = float(ascii_digits(v).strip().rstrip("%").strip().replace(",", ""))
        except ValueError:
            return None
    else:
        return None
    return x if math.isfinite(x) else None


def normalize_profile(data: dict) -> tuple[StudentProfile, list[str]]:
    errors: list[str] = []
    clean: dict = {}
    for key, raw in (data or {}).items():
        if key in FORBIDDEN:
            errors.append(f"'{key}' is not collected by HaqSaathi.")
            continue
        if key not in PROFILE_FIELDS:
            errors.append(f"unknown field '{key}'.")
            continue
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            continue
        if key in VOCAB:
            v = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
            if v not in VOCAB[key]:
                errors.append(f"'{key}' must be one of: {', '.join(sorted(VOCAB[key]))}.")
            else:
                clean[key] = v
        elif key in ("province", "domicile_province"):
            v = PROVINCES.get(str(raw).strip().lower())
            if v is None:
                errors.append(f"'{key}' is not a recognised province or territory.")
            else:
                clean[key] = v
        elif key in RANGES:
            x = _num(raw)
            lo, hi = RANGES[key]
            if x is None:
                errors.append(f"'{key}' must be a number.")
            elif not lo <= x <= hi:
                errors.append(f"'{key}' must be between {lo} and {hi}.")
            else:
                clean[key] = x
        elif key == "receives_other_scholarship":
            if isinstance(raw, bool):
                clean[key] = raw
            else:
                errors.append(f"'{key}' must be true or false.")
        else:  # free text: institution, intended_degree
            v = str(raw).strip()
            if len(v) > MAX_TEXT:
                errors.append(f"'{key}' is too long (max {MAX_TEXT} characters).")
            else:
                clean[key] = v
    return StudentProfile(**clean), errors
