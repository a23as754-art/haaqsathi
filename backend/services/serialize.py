from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum


def to_jsonable(obj):
    """Convert dataclasses / enums / dates to plain JSON types."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(x) for x in obj]
    return obj
