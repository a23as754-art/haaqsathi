import copy, json, tempfile, unittest
from collections import Counter
from datetime import date
from pathlib import Path

from backend.catalog.loader import load_catalog
from backend.evaluation.runner import audit_explanation, load_benchmark, render_report, run_benchmark
from backend.evaluation.run import main
from backend.models.nebius import ModelResult

ROOT = Path(__file__).resolve().parents[2]
CAT = load_catalog(ROOT / "data" / "fixtures" / "catalog.json")
BENCH = load_benchmark(ROOT / "data" / "fixtures" / "benchmark.json")


class RoutingClient:
    """Test double for the live path: answers extraction and explanation prompts differently."""
    def __init__(self): self.calls = 0
    def generate(self, messages, response_schema=None, max_tokens=2048, temperature=0.2):
        self.calls += 1
        if "<student_message>" in messages[-1]["content"]:
            out = {"education_level": "undergraduate"}
        else:
            out = {"summary": "Some conditions look consistent with your answers; others still need checking.", "conditions": []}
        return ModelResult(json.dumps(out), out, 0.25, {"total_tokens": 100})


class BenchmarkFileTests(unittest.TestCase):
    def test_sixty_unique_cases_with_required_coverage(self):
        cases = BENCH["cases"]
        self.assertEqual(len(cases), 60)
        self.assertEqual(len({c["id"] for c in cases}), 60)
        cats = Counter(c["category"] for c in cases)
        for needed in ("straightforward", "ineligible", "missing_or_ambiguous", "outdated_or_conflicting", "urdu",
                       "extraction_ur", "extraction_en", "explain_guard"):
            self.assertGreaterEqual(cats[needed], 4, needed)
        self.assertGreaterEqual(sum(1 for c in cases if c["kind"] == "extraction" and c["expect"].get("no_leak")), 2)

    def test_every_case_declares_expectations(self):
        for c in BENCH["cases"]:
            self.assertIn("expect", c, c["id"]); self.assertIn(c["kind"], ("eligibility", "extraction", "explain"))


class ScriptedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bench_run = run_benchmark(CAT, BENCH, mode="scripted", run_date="2026-10-21")

    def test_all_cases_pass_and_targets_met(self):
        failed = [r["id"] for r in self.bench_run["results"] if not r["passed"]]
        self.assertEqual(failed, [])
        m = self.bench_run["metrics"]
        self.assertGreaterEqual(m["rule_accuracy"]["value"], 0.95)
        self.assertGreaterEqual(m["unknown_handling"]["value"], 0.95)
        self.assertGreaterEqual(m["citation_validity"]["value"], 0.95)
        self.assertEqual(m["unsupported_claims"]["value"], 0)
        self.assertEqual(m["false_not_met"]["value"], 0)
        self.assertGreaterEqual(m["urdu_ledger_completion"]["value"], 0.90)

    def test_model_metrics_are_not_claimed_in_scripted_mode(self):
        m = self.bench_run["metrics"]
        self.assertEqual(m["model_latency"]["status"], "NOT MEASURED")
        self.assertEqual(m["urdu_extraction_relative"]["status"], "NOT MEASURED")

    def test_report_is_honest(self):
        txt = render_report(self.bench_run)
        for must in ("scripted", "NOT MEASURED", "not independent validation"):
            self.assertIn(must, txt)

    def test_deterministic(self):
        again = run_benchmark(CAT, BENCH, mode="scripted", run_date="2026-10-21")
        strip = lambda r: [(x["id"], x["passed"], x["checks"]) for x in r["results"]]
        self.assertEqual(strip(self.bench_run), strip(again))


class RunnerSensitivityTests(unittest.TestCase):
    """The benchmark must be able to fail: it is not allowed to pass whatever the engine does."""
    def test_wrong_expectation_is_caught(self):
        b = copy.deepcopy(BENCH)
        c = [x for x in b["cases"] if x["id"] == "C01"][0]
        c["expect"]["rules"]["hec-level"] = "not_met"          # missing data must never be not_met
        run = run_benchmark(CAT, b, mode="scripted", run_date="2026-10-21")
        self.assertIn("C01", [r["id"] for r in run["results"] if not r["passed"]])
        self.assertLess(run["metrics"]["rule_accuracy"]["value"], 1.0)

    def test_wrong_explain_expectation_is_caught(self):
        b = copy.deepcopy(BENCH)
        [x for x in b["cases"] if x["id"] == "G03"][0]["expect"]["generated_by"] = "model"
        run = run_benchmark(CAT, b, mode="scripted", run_date="2026-10-21")
        self.assertIn("G03", [r["id"] for r in run["results"] if not r["passed"]])

    def test_leak_check_catches_echo(self):
        b = copy.deepcopy(BENCH)
        c = [x for x in b["cases"] if x["id"] == "X05"][0]
        c["expect"]["no_leak"] = "intermediate"                 # this string IS in the output, so the check must fail
        run = run_benchmark(CAT, b, mode="scripted", run_date="2026-10-21")
        self.assertIn("X05", [r["id"] for r in run["results"] if not r["passed"]])

    def test_unknown_mutation_target_rejected(self):
        b = copy.deepcopy(BENCH)
        [x for x in b["cases"] if x["id"] == "D03"][0]["mutate"] = {"no-such-rule": {"verification": "verified"}}
        with self.assertRaises(ValueError): run_benchmark(CAT, b, mode="scripted", run_date="2026-10-21")


class AuditTests(unittest.TestCase):
    def test_audit_flags_bad_text(self):
        from backend.agents.explain import Explanation
        from backend.eligibility.ledger import build_ledger
        from backend.eligibility.models import StudentProfile
        led = build_ledger(CAT.program("hec-nbs"), StudentProfile(), date(2026, 10, 21))
        bad = Explanation("You will receive Rs 99999, see https://x.example", (), "model", None, "needs_verification")
        self.assertEqual(set(audit_explanation(bad, CAT.program("hec-nbs"), led)), {"promise", "link", "number"})
        ok = Explanation("Some conditions still need checking.", (), "model", None, "needs_verification")
        self.assertEqual(audit_explanation(ok, CAT.program("hec-nbs"), led), [])


class LiveModeTests(unittest.TestCase):
    def test_live_mode_calls_client_and_ignores_scripted_outputs(self):
        c = RoutingClient()
        run = run_benchmark(CAT, BENCH, mode="live", client=c, run_date="2026-10-21")
        self.assertEqual(run["mode"], "live")
        self.assertEqual(c.calls, 24)                           # 12 extraction + 12 explanation cases
        self.assertEqual(run["metrics"]["model_latency"]["status"], "MEASURED")
        self.assertNotIn("scripted model outputs", render_report(run).split("## Metrics")[0].lower())

    def test_live_mode_requires_client(self):
        with self.assertRaises(ValueError): run_benchmark(CAT, BENCH, mode="live", run_date="2026-10-21")


class CliTests(unittest.TestCase):
    def test_writes_report_files(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(main(["--mode", "scripted", "--out", d, "--strict"]), 0)
            self.assertTrue((Path(d) / "benchmark-scripted.md").read_text(encoding="utf-8").startswith("# "))
            data = json.loads((Path(d) / "benchmark-scripted.json").read_text(encoding="utf-8"))
            self.assertEqual(data["mode"], "scripted"); self.assertEqual(len(data["results"]), 60)


if __name__ == "__main__":
    unittest.main()
