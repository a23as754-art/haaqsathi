"""Reproducible benchmark runner.

Two modes, always labelled in the report:
  scripted  deterministic: model replies come from the benchmark file, so extraction/explanation rows test OUR
            validation code, not model quality.
  live      a real client is called; model-dependent metrics are measured.
Expected results in the benchmark were written by hand; the runner never derives expectations from the engine.
"""
from __future__ import annotations

import dataclasses
import json
import re
import statistics
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path

from backend.agents.explain import explain_ledger
from backend.agents.extract import extract_profile
from backend.eligibility.ledger import build_ledger
from backend.eligibility.models import StudentProfile
from backend.models.nebius import ModelError, ModelResult
from backend.services.localize import localize_entry
from backend.services.profile import normalize_profile
from backend.services.serialize import to_jsonable
from backend.services.text import ascii_digits

URDU = re.compile(r"[\u0600-\u06ff]")
EXPLAIN_PROFILE = {"education_level": "undergraduate", "institution_sector": "public", "admission_basis": "open_merit"}
BAD_PHRASES = ("guarantee", "will receive", "will be awarded", "definitely", "certainly", "probability",
               "chance of", "100%", "ضمانت", "یقینی")


class ScriptedClient:
    def __init__(self, output=None, error=False):
        self.output, self.error = output, error

    def generate(self, messages, response_schema=None, max_tokens=2048, temperature=0.2):
        if self.error:
            raise ModelError("scripted failure")
        return ModelResult(json.dumps(self.output, ensure_ascii=False), self.output, 0.0, {})


class TimedClient:
    """Wraps a live client to record latency and token usage."""
    def __init__(self, inner):
        self.inner, self.latencies, self.tokens = inner, [], 0

    def generate(self, *a, **k):
        t0 = time.monotonic()
        r = self.inner.generate(*a, **k)
        self.latencies.append(r.latency_s or (time.monotonic() - t0))
        self.tokens += (r.usage or {}).get("total_tokens", 0) or 0
        return r


def load_benchmark(path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [c["id"] for c in data["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    for c in data["cases"]:
        if c["kind"] not in ("eligibility", "extraction", "explain"):
            raise ValueError(f"bad kind in {c['id']}")
    return data


def _check(name, expected, actual, ok=None):
    return {"name": name, "expected": expected, "actual": actual, "ok": (expected == actual) if ok is None else ok}


def audit_explanation(explanation, program, ledger) -> list[str]:
    """Independent safety audit of FINAL user-visible text (digit-level, separate from the product validator)."""
    blob = " ".join([explanation.summary] + [t for _, t in explanation.items])
    problems = []
    if any(p in blob.casefold() for p in BAD_PHRASES):
        problems.append("promise")
    if re.search(r"https?://|www\.", blob, re.I):
        problems.append("link")
    facts = json.dumps(to_jsonable(ledger.entries), ensure_ascii=False) + program.name
    allowed = set(re.findall(r"\d+", ascii_digits(facts))) | {str(i) for i in range(len(ledger.entries) + 1)}
    if set(re.findall(r"\d+", ascii_digits(blob))) - allowed:
        problems.append("number")
    return problems


def _mutated(program, mutate):
    by_id = {r.id: r for r in program.rules}
    for rid in mutate:
        if rid not in by_id:
            raise ValueError(f"mutate targets unknown rule {rid!r}")
    rules = []
    for r in program.rules:
        m = mutate.get(r.id)
        if m:
            m = {k: (date.fromisoformat(v) if k in ("effective_from", "effective_until") else v) for k, v in m.items()}
            r = dataclasses.replace(r, **m)
        rules.append(r)
    return dataclasses.replace(program, rules=tuple(rules))


def _citation_ok(e, sources) -> bool:
    s = sources.get(e.source_document_id)
    return bool(s and e.source_url == s.url and e.source_url.startswith("https://") and e.source_passage
                and e.source_last_checked == s.last_checked)


def _urdu_complete(e) -> bool:
    t = localize_entry(e, "ur")
    parts = [t["requirement"], t["reason"], t["next_action"]] + ([t["ambiguity"]] if t["ambiguity"] else [])
    return t["language"] == "ur" and all(URDU.search(p) for p in parts)


def _run_eligibility(catalog, case, default_today):
    t0 = time.perf_counter()
    profile, errors = normalize_profile(case["profile"])
    program = _mutated(catalog.program(case["program"]), case.get("mutate", {}))
    today = date.fromisoformat(case["today"]) if case.get("today") else default_today
    ledger = build_ledger(program, profile, today)
    actual = {e.rule_id: e.status.value for e in ledger.entries}
    ex = case["expect"]
    checks, rule_checks = [], []
    for rid, want in ex["rules"].items():
        got = actual.get(rid)
        checks.append(_check(f"rule:{rid}", want, got)); rule_checks.append({"rule": rid, "expected": want, "actual": got})
    checks.append(_check("status", ex["status"], ledger.status.value))
    if ex.get("no_not_met"):
        checks.append(_check("no_not_met", True, "not_met" not in actual.values()))
    if "profile_errors" in ex:
        checks.append(_check("profile_errors", ex["profile_errors"], len(errors)))
    for rid in ex.get("ambiguity_present", []):
        e = [x for x in ledger.entries if x.rule_id == rid][0]
        checks.append(_check(f"ambiguity:{rid}", True, bool(e.ambiguity)))
    urdu = None
    if ex.get("urdu_complete"):
        urdu = all(_urdu_complete(e) for e in ledger.entries)
        checks.append(_check("urdu_complete", True, urdu))
    return {"checks": checks, "rule_checks": rule_checks, "urdu_complete": urdu,
            "citations": [_citation_ok(e, catalog.sources) for e in ledger.entries],
            "elapsed_ms": (time.perf_counter() - t0) * 1000}


def _run_extraction(case, mode, client):
    cl = ScriptedClient(case["model_output"]) if mode == "scripted" else client
    try:
        ext = extract_profile(cl, case["text"])
    except ModelError as e:
        return {"checks": [_check("model_call", "ok", str(e), False)], "profile_ok": False, "leak": False}
    actual = {k: v for k, v in asdict(ext.profile).items() if v is not None}
    ex = case["expect"]
    checks = [_check("profile", ex["profile"], actual)]
    if mode == "scripted" and "warnings" in ex:
        checks.append(_check("warnings", ex["warnings"], len(ext.warnings)))
    leak = False
    if ex.get("no_leak"):
        blob = json.dumps(actual, ensure_ascii=False) + " ".join(ext.warnings)
        leak = ex["no_leak"] in blob
        checks.append(_check("no_leak", False, leak))
    return {"checks": checks, "profile_ok": checks[0]["ok"], "leak": leak}


def _run_explain(catalog, case, mode, client, today):
    program = catalog.program("hec-nbs")
    ledger = build_ledger(program, StudentProfile(**EXPLAIN_PROFILE), today)
    cl = ScriptedClient(case.get("model_output"), error=bool(case.get("model_error"))) if mode == "scripted" else client
    ex = explain_ledger(cl, program, ledger, case["language"])
    problems = audit_explanation(ex, program, ledger)
    checks = [_check("status_unchanged", ledger.status.value, ex.status),
              _check("expected_status", case["expect"]["status"], ex.status),
              _check("audit_clean", [], problems)]
    if mode == "scripted":
        checks.append(_check("generated_by", case["expect"]["generated_by"], ex.generated_by))
    return {"checks": checks, "audit_problems": problems, "generated_by": ex.generated_by}


def _judge(value, op, target):
    ok = {">=": value >= target, "==": value == target}[op]
    return "PASS" if ok else "FAIL"


def _metric(value, op=None, target=None, status=None, notes=""):
    return {"value": value, "target": f"{op} {target}" if op else "-",
            "status": status or (_judge(value, op, target) if op else "MEASURED"), "notes": notes}


def _not_measured(why):
    return {"value": None, "target": "-", "status": "NOT MEASURED", "notes": why}


def _rate(num, den):
    return (num / den) if den else 0.0


def run_benchmark(catalog, bench, mode="scripted", client=None, run_date=None) -> dict:
    if mode not in ("scripted", "live"):
        raise ValueError("mode must be 'scripted' or 'live'")
    if mode == "live" and client is None:
        raise ValueError("live mode needs a model client")
    timed = TimedClient(client) if mode == "live" else None
    today = date.fromisoformat(bench["today"])
    results = []
    for c in bench["cases"]:
        if c["kind"] == "eligibility":
            r = _run_eligibility(catalog, c, today)
        elif c["kind"] == "extraction":
            r = _run_extraction(c, mode, timed)
        else:
            r = _run_explain(catalog, c, mode, timed, today)
        r.update(id=c["id"], category=c["category"], kind=c["kind"], passed=all(k["ok"] for k in r["checks"]))
        results.append(r)

    elig = [r for r in results if r["kind"] == "eligibility"]
    rc = [x for r in elig for x in r["rule_checks"]]
    unk = [x for x in rc if x["expected"] == "unknown"]
    cites = [b for r in elig for b in r["citations"]]
    urdu = [r for r in elig if r["category"] == "urdu"]
    ext = [r for r in results if r["kind"] == "extraction"]
    exp = [r for r in results if r["kind"] == "explain"]
    en = [r for r in ext if r["category"] == "extraction_en"]
    ur = [r for r in ext if r["category"] == "extraction_ur"]
    en_acc, ur_acc = _rate(sum(r["profile_ok"] for r in en), len(en)), _rate(sum(r["profile_ok"] for r in ur), len(ur))
    lat = sorted(r["elapsed_ms"] for r in elig)
    m = {
        "rule_accuracy": _metric(_rate(sum(x["expected"] == x["actual"] for x in rc), len(rc)), ">=", 0.95, notes=f"{len(rc)} rule-level checks"),
        "unknown_handling": _metric(_rate(sum(x["expected"] == x["actual"] for x in unk), len(unk)), ">=", 0.95, notes=f"{len(unk)} checks where unknown was the right answer"),
        "false_not_met": _metric(sum(1 for x in rc if x["actual"] == "not_met" and x["expected"] != "not_met"), "==", 0, notes="a student wrongly told a condition is not met"),
        "citation_validity": _metric(_rate(sum(cites), len(cites)), ">=", 0.95, notes=f"{len(cites)} ledger entries; source url, passage and check date must match the catalog"),
        "unsupported_claims": _metric(sum(1 for r in exp if r["audit_problems"]), "==", 0, notes="independent audit of final user-visible explanations"),
        "extraction_leaks": _metric(sum(1 for r in ext if r["leak"]), "==", 0, notes="sensitive strings echoed in profile or warnings"),
        "urdu_ledger_completion": _metric(_rate(sum(r["urdu_complete"] for r in urdu), len(urdu)), ">=", 0.90, notes="every ledger entry fully in Urdu (reasoning text only, not model quality)"),
        "eligibility_latency_ms": _metric(round(statistics.median(lat), 3), notes=f"median per case; max {round(lat[-1], 3)} ms (deterministic code, no model)"),
        "extraction_accuracy_en": _metric(en_acc, notes=f"{len(en)} cases, {mode} mode"),
        "extraction_accuracy_ur": _metric(ur_acc, notes=f"{len(ur)} cases, {mode} mode"),
    }
    if mode == "scripted":
        m["guard_decisions"] = _metric(_rate(sum(next(k for k in r["checks"] if k["name"] == "generated_by")["ok"] for r in exp), len(exp)),
                                       ">=", 0.95, notes="explanations accepted/rejected as expected (tests our validator on scripted replies)")
        m["urdu_extraction_relative"] = _not_measured("needs a live model; scripted mode only exercises the validation pipeline")
        m["model_latency"] = _not_measured("no model was called")
    else:
        m["guard_decisions"] = _metric(_rate(sum(r["generated_by"] == "model" for r in exp), len(exp)), notes="share of live explanations accepted by the validator (rest fell back to the template)")
        m["urdu_extraction_relative"] = _metric(_rate(ur_acc, en_acc) if en_acc else 0.0, ">=", 0.90, notes="Urdu extraction accuracy relative to English, live model")
        lats = timed.latencies
        m["model_latency"] = _metric(round(statistics.median(lats), 3) if lats else None, status="MEASURED",
                                     notes=f"median seconds per call over {len(lats)} calls; max {round(max(lats), 3) if lats else None}; total tokens {timed.tokens}")
    m["retrieval_recall"] = _not_measured("no document retrieval layer exists yet; the catalog is curated and looked up directly")
    m["end_to_end_success"] = _not_measured("needs real-browser tests; the web app has not been run in an automated browser")
    return {"mode": mode, "run_date": run_date, "benchmark_description": bench.get("description", ""),
            "results": results, "metrics": m}


def render_report(run: dict) -> str:
    mode, m, res = run["mode"], run["metrics"], run["results"]
    out = [f"# HaqSaathi benchmark report ({mode} mode)", "",
           f"Run date: {run.get('run_date') or 'n/a'}  |  Cases: {len(res)}  |  Passed: {sum(r['passed'] for r in res)}", "",
           f"> {run['benchmark_description']}", ">"]
    if mode == "scripted":
        out.append("> Scripted mode: extraction and explanation rows run our validation code against scripted model replies. They say nothing about real model quality.")
    else:
        out.append("> Live mode: extraction and explanation cases call the configured model; scripted replies in the benchmark file are ignored.")
    out += ["", "## Metrics", "", "| Metric | Value | Target | Status | Notes |", "|---|---|---|---|---|"]
    for name, v in m.items():
        val = "-" if v["value"] is None else (f"{v['value']:.3f}" if isinstance(v["value"], float) else str(v["value"]))
        out.append(f"| {name} | {val} | {v['target']} | {v['status']} | {v['notes']} |")
    cats = defaultdict(lambda: [0, 0])
    for r in res:
        cats[r["category"]][0] += 1; cats[r["category"]][1] += r["passed"]
    out += ["", "## Results by category", "", "| Category | Cases | Passed |", "|---|---|---|"]
    out += [f"| {c} | {n} | {p} |" for c, (n, p) in cats.items()]
    failed = [r for r in res if not r["passed"]]
    out += ["", "## Failed cases", ""]
    if not failed:
        out.append("None.")
    for r in failed:
        bad = "; ".join(f"{k['name']} expected {k['expected']!r} got {k['actual']!r}" for k in r["checks"] if not k["ok"])
        out.append(f"- {r['id']} ({r['category']}): {bad}")
    out += ["", "## Limitations", "",
            "- Cases are synthetic and the expected results were written by the same author as the engine: not independent validation.",
            "- Catalog has 2 programs; results do not generalise to other scholarships.",
            "- Metrics marked NOT MEASURED were not run and must not be quoted as results."]
    return "\n".join(out) + "\n"
