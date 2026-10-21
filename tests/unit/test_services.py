import json, unittest
from datetime import date
from pathlib import Path

from backend.catalog.loader import load_catalog
from backend.eligibility.checklist import build_action_plan
from backend.eligibility.ledger import build_ledger
from backend.eligibility.models import OpportunityStatus as O, StudentProfile
from backend.services.profile import normalize_profile
from backend.services.search import search_opportunities
from backend.services.serialize import to_jsonable
from backend.services.sources import describe_source

CAT = load_catalog(Path(__file__).resolve().parents[2] / "data" / "fixtures" / "catalog.json")
TODAY = date(2026, 10, 21)


class ProfileTests(unittest.TestCase):
    def test_normalizes_vocab_and_numbers(self):
        p, errs = normalize_profile({"education_level": " Undergraduate ", "domicile_province": "kpk",
                                     "marks_percent": "72.5", "institution_sector": "PUBLIC"})
        self.assertEqual(errs, [])
        self.assertEqual((p.education_level, p.domicile_province, p.marks_percent, p.institution_sector),
                         ("undergraduate", "Khyber Pakhtunkhwa", 72.5, "public"))

    def test_empty_values_dropped(self):
        p, errs = normalize_profile({"province": "", "cgpa": None})
        self.assertEqual((errs, p), ([], StudentProfile()))

    def test_bad_vocab_and_ranges_reported(self):
        _, errs = normalize_profile({"education_level": "wizard", "marks_percent": 140, "cgpa": 9,
                                     "monthly_family_income_pkr": -5})
        self.assertEqual(len(errs), 4)

    def test_non_numeric_rejected_and_bool_rejected(self):
        _, errs = normalize_profile({"marks_percent": "abc", "cgpa": True})
        self.assertEqual(len(errs), 2)

    def test_scholarship_flag_must_be_bool(self):
        _, errs = normalize_profile({"receives_other_scholarship": "yes"})
        self.assertEqual(len(errs), 1)

    def test_sensitive_and_unknown_keys_rejected(self):
        _, errs = normalize_profile({"cnic": "12345-1234567-1", "favourite_colour": "blue"})
        self.assertEqual(len(errs), 2)
        self.assertTrue(any("not collected" in e for e in errs))
        self.assertFalse(any("12345" in e for e in errs))   # never echo sensitive values

    def test_long_free_text_rejected(self):
        _, errs = normalize_profile({"institution": "x" * 500})
        self.assertEqual(len(errs), 1)


class SearchTests(unittest.TestCase):
    def test_returns_all_programs_with_counts(self):
        res = search_opportunities(CAT, StudentProfile(education_level="undergraduate", institution_sector="public",
                                                       admission_basis="open_merit"), TODAY)
        self.assertEqual({r.program.id for r in res}, {"hec-nbs", "peef-master"})
        hec = [r for r in res if r.program.id == "hec-nbs"][0]
        self.assertEqual(hec.counts["met"], 3)

    def test_likely_not_eligible_ranked_after_needs_verification(self):
        res = search_opportunities(CAT, StudentProfile(education_level="undergraduate", institution_sector="public",
                                                       admission_basis="open_merit"), TODAY)
        order = [r.ledger.status for r in res]
        self.assertEqual(order, [O.NEEDS_VERIFICATION, O.LIKELY_NOT_ELIGIBLE])

    def test_no_numeric_score_exposed(self):
        res = search_opportunities(CAT, StudentProfile(), TODAY)
        self.assertFalse(any(hasattr(r, "score") or hasattr(r, "match_percent") for r in res))


class ChecklistTests(unittest.TestCase):
    def plan(self, pid, **p):
        prog = CAT.program(pid)
        return build_action_plan(prog, build_ledger(prog, StudentProfile(**p), TODAY))

    def test_missing_info_items_come_first_and_name_fields(self):
        items = self.plan("hec-nbs", education_level="undergraduate")
        self.assertEqual(items[0].kind, "provide_info")
        self.assertTrue(any("admission" in i.text.lower() for i in items if i.kind == "provide_info"))

    def test_verify_items_for_unevaluable_conditions(self):
        items = self.plan("hec-nbs", education_level="undergraduate", institution_sector="public", admission_basis="open_merit")
        texts = " ".join(i.text for i in items if i.kind == "verify")
        self.assertIn("financial aid office", texts)

    def test_window_is_never_assumed_open(self):
        items = self.plan("hec-nbs", education_level="undergraduate", institution_sector="public", admission_basis="open_merit")
        self.assertTrue(any(i.kind == "verify" and "deadline" in i.text.lower() for i in items))

    def test_not_met_produces_review_item_and_no_apply_item(self):
        items = self.plan("hec-nbs", education_level="undergraduate", institution_sector="public", admission_basis="self_finance")
        self.assertTrue(any(i.kind == "review" for i in items))
        self.assertFalse(any(i.kind == "apply" for i in items))

    def test_no_duplicate_items(self):
        items = self.plan("peef-master")
        texts = [i.text for i in items]
        self.assertEqual(len(texts), len(set(texts)))

    def test_no_guarantee_language(self):
        for pid in ("hec-nbs", "peef-master"):
            blob = " ".join(i.text.lower() for i in self.plan(pid))
            for bad in ("guarantee", "you will receive", "you will get", "approved"):
                self.assertNotIn(bad, blob)


class SerializeAndSourceTests(unittest.TestCase):
    def test_to_jsonable_roundtrips_through_json(self):
        prog = CAT.program("hec-nbs")
        led = build_ledger(prog, StudentProfile(education_level="undergraduate"), TODAY)
        out = json.loads(json.dumps(to_jsonable(led), ensure_ascii=False))
        self.assertEqual(out["status"], "needs_verification")
        self.assertEqual(out["entries"][0]["status"], "met")
        self.assertEqual(out["entries"][0]["source_last_checked"], "2026-10-20")

    def test_source_freshness(self):
        s = CAT.sources["hec-nbs-faq"]
        d = describe_source(s, TODAY)
        self.assertEqual((d["age_days"], d["stale"], d["tier"]), (1, False, "A"))
        self.assertTrue(describe_source(s, date(2027, 1, 1))["stale"])
        self.assertIn("official", d["tier_label"].lower())


if __name__ == "__main__":
    unittest.main()
