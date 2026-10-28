import re, unittest
from datetime import date
from pathlib import Path

from backend.agents.explain import explain_ledger
from backend.catalog.loader import load_catalog
from backend.eligibility.checklist import build_action_plan
from backend.eligibility.engine import evaluate_rule
from backend.eligibility.ledger import build_ledger
from backend.eligibility.models import Rule, StudentProfile
from backend.eligibility.reasons import REASONS
from backend.services.localize import localize_entry

CAT = load_catalog(Path(__file__).resolve().parents[2] / "data" / "fixtures" / "catalog.json")
TODAY = date(2026, 10, 21)
URDU = re.compile(r"[\u0600-\u06ff]")
HEC, PEEF = CAT.program("hec-nbs"), CAT.program("peef-master")


class CatalogUrduCompleteness(unittest.TestCase):
    def test_every_rule_has_urdu_text(self):
        for p in CAT.programs:
            for r in p.rules:
                self.assertTrue(r.description_ur and URDU.search(r.description_ur), r.id)
                self.assertTrue(r.next_action_ur and URDU.search(r.next_action_ur), r.id)
                if r.ambiguity:
                    self.assertTrue(r.ambiguity_ur and URDU.search(r.ambiguity_ur), r.id)

    def test_every_unevaluable_and_program_note_has_urdu(self):
        for p in CAT.programs:
            self.assertTrue(URDU.search(p.application_note_ur or ""), p.id)
            for u in p.unevaluable:
                self.assertTrue(URDU.search(u.description_ur or "") and URDU.search(u.next_action_ur or ""), u.id)
                if u.ambiguity:
                    self.assertTrue(URDU.search(u.ambiguity_ur or ""), u.id)


class ReasonCodes(unittest.TestCase):
    def test_every_reason_has_both_languages(self):
        for code, v in REASONS.items():
            self.assertTrue(v["en"] and URDU.search(v["ur"]), code)

    def rule(self, **kw):
        base = dict(id="r", field="province", op="eq", value="Sindh", description="d", verification="verified",
                    last_checked=date(2026, 10, 20))
        base.update(kw); return Rule(**base)

    def test_all_engine_paths_set_known_reason_codes(self):
        P = StudentProfile
        cases = [
            (self.rule(), P(province="Sindh")), (self.rule(), P(province="Punjab")), (self.rule(), P()),
            (self.rule(field="marks_percent", op="gte", value=1), P(marks_percent="x")),
            (self.rule(verification="conflicting"), P()), (self.rule(verification="unverified"), P()),
            (self.rule(effective_from=date(2027, 1, 1)), P()), (self.rule(effective_until=date(2026, 1, 1)), P()),
            (self.rule(last_checked=date(2026, 1, 1)), P()),
            (self.rule(field="*", op="any_of", value=(("marks_percent", "gte", 60), ("cgpa", "gte", 2.5))), P(marks_percent=70)),
            (self.rule(field="*", op="any_of", value=(("marks_percent", "gte", 60), ("cgpa", "gte", 2.5))), P(marks_percent=10, cgpa=1)),
            (self.rule(field="*", op="any_of", value=(("marks_percent", "gte", 60), ("cgpa", "gte", 2.5))), P()),
        ]
        codes = set()
        for r, p in cases:
            res = evaluate_rule(r, p, TODAY)
            self.assertIn(res.reason_code, REASONS); self.assertEqual(res.reason, REASONS[res.reason_code]["en"])
            codes.add(res.reason_code)
        self.assertEqual(len(codes), 12)

    def test_unevaluable_entries_have_reason_code(self):
        led = build_ledger(HEC, StudentProfile(), TODAY)
        self.assertEqual([e.reason_code for e in led.entries[-2:]], ["unevaluable"] * 2)


class LocalizeEntryTests(unittest.TestCase):
    def entry(self, rid, **p):
        led = build_ledger(HEC, StudentProfile(**p), TODAY)
        return [e for e in led.entries if e.rule_id == rid][0]

    def test_urdu_entry_is_fully_urdu(self):
        t = localize_entry(self.entry("hec-level", education_level="undergraduate"), "ur")
        self.assertEqual(t["language"], "ur")
        for k in ("requirement", "reason", "next_action"):
            self.assertTrue(URDU.search(t[k]), k)

    def test_english_entry(self):
        t = localize_entry(self.entry("hec-level"), "en")
        self.assertEqual(
    (t["language"], t["requirement"]),
    ("en", "Education level is undergraduate"),
)

    def test_falls_back_to_english_when_urdu_missing(self):
        r = Rule(id="x", field="province", op="eq", value="Sindh", description="Needs Sindh", verification="verified",
                 last_checked=date(2026, 10, 20))
        t = localize_entry(evaluate_rule(r, StudentProfile(province="Sindh"), TODAY), "ur")
        self.assertEqual((t["language"], t["requirement"]), ("en", "Needs Sindh"))
        self.assertTrue(URDU.search(t["reason"]))     # reason codes are always translated

    def test_ambiguity_localized_only_when_present(self):
        self.assertIsNone(localize_entry(self.entry("hec-level"), "ur")["ambiguity"])
        self.assertTrue(URDU.search(localize_entry(self.entry("hec-public"), "ur")["ambiguity"]))


class UrduChecklistTests(unittest.TestCase):
    def plan(self, prog, lang, **p):
        return build_action_plan(prog, build_ledger(prog, StudentProfile(**p), TODAY), lang)

    def test_same_structure_as_english(self):
        en = self.plan(HEC, "en", education_level="undergraduate"); ur = self.plan(HEC, "ur", education_level="undergraduate")
        self.assertEqual([i.kind for i in en], [i.kind for i in ur])

    def test_urdu_items_are_urdu_and_not_english_actions(self):
        ur = self.plan(HEC, "ur", education_level="undergraduate", institution_sector="public", admission_basis="open_merit")
        for i in ur: self.assertTrue(URDU.search(i.text), i.text)
        blob = " ".join(i.text for i in ur)
        self.assertNotIn("financial aid office", blob)
        self.assertIn("فنانشل ایڈ آفس", blob)

    def test_urdu_missing_info_names_fields_in_urdu(self):
        ur = self.plan(PEEF, "ur")
        self.assertTrue(any("ڈومیسائل" in i.text for i in ur if i.kind == "provide_info"))

    def test_urdu_not_met_has_review_and_no_apply(self):
        ur = self.plan(HEC, "ur", education_level="undergraduate", institution_sector="public", admission_basis="self_finance")
        self.assertTrue(any(i.kind == "review" for i in ur)); self.assertFalse(any(i.kind == "apply" for i in ur))

    def test_no_guarantee_language_in_urdu(self):
        for prog in (HEC, PEEF):
            blob = " ".join(i.text for i in self.plan(prog, "ur"))
            for bad in ("ضمانت", "یقینی"):
                self.assertNotIn(bad, blob)

    def test_default_language_unchanged(self):
        self.assertEqual([i.text for i in self.plan(HEC, "en")],
                         [i.text for i in build_action_plan(HEC, build_ledger(HEC, StudentProfile(), TODAY))])


class UrduTemplateExplanation(unittest.TestCase):
    def test_template_uses_urdu_requirements(self):
        led = build_ledger(HEC, StudentProfile(education_level="undergraduate"), TODAY)
        e = explain_ledger(None, HEC, led, "ur")
        for _, text in e.items: self.assertTrue(URDU.search(text), text)


if __name__ == "__main__":
    unittest.main()
