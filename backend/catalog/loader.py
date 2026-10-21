"""Load and validate the curated scholarship catalog.

Policy enforced here (not left to convention):
  * every rule cites a known source;
  * a `verified` rule may only cite a tier A (official body) or tier B (official institution) source;
  * ids are unique; dates are ISO; rules pass the same validation as Rule itself.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from backend.eligibility.models import Rule

TIERS = ("A", "B", "C")


class CatalogError(ValueError):
    pass


def _date(s, where):
    if s in (None, ""):
        return None
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise CatalogError(f"{where}: bad ISO date {s!r}") from None


def _tuplify(v):
    return tuple(_tuplify(x) for x in v) if isinstance(v, list) else v


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    title: str
    tier: str
    published: date | None
    last_checked: date
    retrieval: str          # fetched | search_snippet | manual
    note: str | None = None


@dataclass(frozen=True)
class Unevaluable:
    """A real condition that cannot be checked from the profile. Always shown as `unknown`."""
    id: str
    description: str
    source_id: str
    passage: str
    next_action: str
    ambiguity: str | None = None
    source_url: str | None = None
    source_published: date | None = None
    source_last_checked: date | None = None


@dataclass(frozen=True)
class Program:
    id: str
    name: str
    organization: str
    level: str
    description: str
    rules: tuple
    unevaluable: tuple
    application_confirmed_open: bool
    application_deadline: date | None
    application_url: str | None
    application_note: str
    closure_evidenced: bool


@dataclass(frozen=True)
class Catalog:
    sources: dict
    programs: tuple

    def program(self, pid: str) -> Program:
        for p in self.programs:
            if p.id == pid:
                return p
        raise KeyError(pid)


def load_catalog(src) -> Catalog:
    data = src if isinstance(src, dict) else json.loads(Path(src).read_text(encoding="utf-8"))
    sources: dict[str, Source] = {}
    for sid, s in data.get("sources", {}).items():
        if s.get("tier") not in TIERS:
            raise CatalogError(f"source {sid}: bad tier")
        lc = _date(s.get("last_checked"), f"source {sid}.last_checked")
        if lc is None:
            raise CatalogError(f"source {sid}: last_checked is required")
        sources[sid] = Source(sid, s["url"], s["title"], s["tier"], _date(s.get("published"), f"source {sid}.published"),
                              lc, s.get("retrieval", "manual"), s.get("note"))

    seen_programs, seen_rules, programs = set(), set(), []
    for p in data.get("programs", []):
        if p["id"] in seen_programs:
            raise CatalogError(f"duplicate program id {p['id']}")
        seen_programs.add(p["id"])
        rules = []
        for r in p.get("rules", []):
            if r["id"] in seen_rules:
                raise CatalogError(f"duplicate rule id {r['id']}")
            seen_rules.add(r["id"])
            src = sources.get(r.get("source_id"))
            if src is None:
                raise CatalogError(f"rule {r['id']}: unknown source {r.get('source_id')!r}")
            verification = r.get("verification", "unverified")
            if verification == "verified" and src.tier not in ("A", "B"):
                raise CatalogError(f"rule {r['id']}: verified rules must cite a tier A/B source")
            try:
                rules.append(Rule(
                    id=r["id"], field=r["field"], op=r["op"], value=_tuplify(r["value"]),
                    description=r["description"], verification=verification,
                    source_document_id=src.id, source_url=src.url, source_passage=r.get("passage"),
                    source_published=src.published, last_checked=src.last_checked,
                    version=r.get("version", "1"),
                    effective_from=_date(r.get("effective_from"), f"rule {r['id']}.effective_from"),
                    effective_until=_date(r.get("effective_until"), f"rule {r['id']}.effective_until"),
                    next_action=r.get("next_action", "Check the official source for the current requirement."),
                    ambiguity=r.get("ambiguity")))
            except ValueError as e:
                if isinstance(e, CatalogError):
                    raise
                raise CatalogError(f"rule {r['id']}: {e}") from None
        unev = []
        for u in p.get("unevaluable", []):
            if u["source_id"] not in sources:
                raise CatalogError(f"unevaluable {u['id']}: unknown source")
            if u["id"] in seen_rules:
                raise CatalogError(f"duplicate id {u['id']}")
            seen_rules.add(u["id"])
            us = sources[u["source_id"]]
            unev.append(Unevaluable(u["id"], u["description"], u["source_id"], u["passage"],
                                    u["next_action"], u.get("ambiguity"), us.url, us.published, us.last_checked))
        app = p.get("application", {})
        programs.append(Program(
            id=p["id"], name=p["name"], organization=p["organization"], level=p["level"],
            description=p["description"], rules=tuple(rules), unevaluable=tuple(unev),
            application_confirmed_open=bool(app.get("confirmed_open", False)),
            application_deadline=_date(app.get("deadline"), f"{p['id']}.deadline"),
            application_url=app.get("url"), application_note=app.get("note", ""),
            closure_evidenced=bool(app.get("closure_evidenced", False))))
    return Catalog(sources=sources, programs=tuple(programs))
