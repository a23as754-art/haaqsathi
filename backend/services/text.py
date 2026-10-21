from __future__ import annotations

_ARABIC_INDIC = {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}
_EXT_ARABIC_INDIC = {ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}
DIGIT_MAP = {**_ARABIC_INDIC, **_EXT_ARABIC_INDIC, ord("٫"): ".", ord("٬"): ","}


def ascii_digits(s: str) -> str:
    """Map Arabic-Indic and Urdu digits to ASCII so numbers parse and compare reliably."""
    return s.translate(DIGIT_MAP)


def detect_language(text: str) -> str:
    """'ur' if Arabic-script letters outnumber Latin letters, else 'en'."""
    arabic = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff" and not ch.isdigit())
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "ur" if arabic > latin else "en"
