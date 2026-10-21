from __future__ import annotations

from datetime import date

TIER_LABELS = {
    "A": "Official body (primary source)",
    "B": "Official institution page",
    "C": "Secondary source (lead only, never establishes a rule)",
}


def describe_source(source, today: date, max_age_days: int = 30) -> dict:
    age = (today - source.last_checked).days
    return {
        "id": source.id, "url": source.url, "title": source.title, "tier": source.tier,
        "tier_label": TIER_LABELS[source.tier],
        "published": source.published.isoformat() if source.published else None,
        "last_checked": source.last_checked.isoformat(),
        "age_days": age, "stale": age > max_age_days,
        "retrieval": source.retrieval, "note": source.note,
    }
