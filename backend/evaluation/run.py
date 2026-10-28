"""CLI: python -m backend.evaluation.run [--mode scripted|live] [--out reports] [--strict]"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from backend.catalog.loader import load_catalog
from backend.evaluation.runner import load_benchmark, render_report, run_benchmark
from backend.services.serialize import to_jsonable

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the HaqSaathi benchmark and save a report.")
    ap.add_argument("--mode", choices=["scripted", "live"], default="scripted")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    ap.add_argument("--catalog", default=str(ROOT / "data" / "fixtures" / "catalog.json"))
    ap.add_argument("--benchmark", default=str(ROOT / "data" / "fixtures" / "benchmark.json"))
    ap.add_argument("--strict", action="store_true", help="exit 1 if any case fails or any target is missed")
    a = ap.parse_args(argv)

    client = None
    if a.mode == "live":
        from backend.models.nebius import ModelError, NebiusClient
        try:
            client = NebiusClient()
        except ModelError as e:
            print(f"live mode needs NEBIUS_API_KEY and NEBIUS_MODEL: {e}")
            return 2

    run = run_benchmark(load_catalog(a.catalog), load_benchmark(a.benchmark), mode=a.mode, client=client,
                        run_date=date.today().isoformat())
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    (out / f"benchmark-{a.mode}.md").write_text(render_report(run), encoding="utf-8")
    (out / f"benchmark-{a.mode}.json").write_text(json.dumps(to_jsonable(run), ensure_ascii=False, indent=1), encoding="utf-8")

    failed = [r["id"] for r in run["results"] if not r["passed"]]
    missed = [k for k, v in run["metrics"].items() if v["status"] == "FAIL"]
    print(f"mode={a.mode} cases={len(run['results'])} failed={failed or 'none'} targets_missed={missed or 'none'}")
    print(f"report: {out / ('benchmark-' + a.mode + '.md')}")
    return 1 if a.strict and (failed or missed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
