import unittest
from datetime import date
from pathlib import Path

from backend.catalog.loader import load_catalog
from backend.eligibility.ledger import build_ledger
from backend.eligibility.models import ConditionStatus as C, OpportunityStatus as O, StudentProfile

CAT = load_catalog(Path(__file__).resolve().parents[2] / "data" / "fixtures" / "catalog.json")
HEC, PEEF = CAT.program("hec-nbs"), CAT.program("peef-master")
TODAY = date(2026, 10, 21)


def statuses(ledger):
    return {e.rule_id: e.status for e in ledger.entries}


class HecLedgerTests(unittest.TestCase):
    base = dict(education_level="undergraduate", institution_sector="public", admission_basis="open_merit")

    def test_all_checkable_met_but_needs_verification(self):
        led = build_ledger(HEC, StudentProfile(**self.base), TODAY)
        s = statuses(led)
        self.assertEqual([s["hec-level"], s["hec-public"], s["hec-not-self-finance"]], [C.MET] * 3)
        self.assertIn(C.UNKNOWN, s.values())          # need assessment + participating list
        self.assertEqual(led.status, O.NEEDS_VERIFICATION)

    def test_self_finance_is_likely_not_eligible_with_evidence(self):
        led = build_ledger(HEC, StudentProfile(**{**self.base, "admission_basis": "self_finance"}), TODAY)
        self.assertEqual(led.status, O.LIKELY_NOT_ELIGIBLE)
        bad = [e for e in led.entries if e.status == C.NOT_MET][0]
        self.assertTrue(bad.source_url.startswith("https://www.hec.gov.pk/"))
        self.assertTrue(bad.source_passage)

    def test_missing_admission_basis_is_unknown(self):
        p = {k: v for k, v in self.base.items() if k != "admission_basis"}
        e = {x.rule_id: x for x in build_ledger(HEC, StudentProfile(**p), TODAY).entries}["hec-not-self-finance"]
        self.assertEqual((e.status, e.missing_fields), (C.UNKNOWN, ("admission_basis",)))

    def test_stale_sources_never_produce_not_met(self):
        late = date(2027, 3, 1)
        led = build_ledger(HEC, StudentProfile(**{**self.base, "admission_basis": "self_finance"}), late)
        self.assertNotIn(C.NOT_MET, statuses(led).values())
        self.assertEqual(led.status, O.NEEDS_VERIFICATION)

    def test_unknown_entries_always_have_next_action(self):
        led = build_ledger(HEC, StudentProfile(), TODAY)
        for e in led.entries:
            if e.status == C.UNKNOWN: self.assertTrue(e.next_action)


class PeefLedgerTests(unittest.TestCase):
    ok = dict(education_level="masters", domicile_province="Punjab", marks_percent=65,
              receives_other_scholarship=False, monthly_family_income_pkr=30000)

    def test_income_rule_stays_unknown_so_status_needs_verification(self):
        led = build_ledger(PEEF, StudentProfile(**self.ok), TODAY)
        s = statuses(led)
        self.assertEqual(s["peef-income"], C.UNKNOWN)
        self.assertEqual(s["peef-domicile"], C.MET)
        self.assertEqual(s["peef-marks"], C.MET)
        self.assertEqual(led.status, O.NEEDS_VERIFICATION)

    def test_other_domicile_not_met(self):
        led = build_ledger(PEEF, StudentProfile(**{**self.ok, "domicile_province": "Sindh"}), TODAY)
        self.assertEqual(statuses(led)["peef-domicile"], C.NOT_MET)
        self.assertEqual(led.status, O.LIKELY_NOT_ELIGIBLE)

    def test_cgpa_alternative_works(self):
        p = {k: v for k, v in self.ok.items() if k != "marks_percent"}
        led = build_ledger(PEEF, StudentProfile(**p, cgpa=3.1), TODAY)
        self.assertEqual(statuses(led)["peef-marks"], C.MET)


class NeverOverclaimTests(unittest.TestCase):
    def test_no_program_is_potential_match_or_closed_today(self):
        for p in CAT.programs:
            led = build_ledger(p, StudentProfile(), TODAY)
            self.assertNotIn(led.status, (O.POTENTIAL_MATCH, O.CLOSED))


if __name__ == "__main__":
    unittest.main()
