import unittest
from datetime import date

from backend.eligibility.models import (ConditionStatus as C, OpportunityStatus as O,
                                        Rule, StudentProfile)
from backend.eligibility.engine import evaluate_rule, evaluate_all, derive_opportunity_status

TODAY = date(2026, 10, 20)


def rule(**kw):
    base = dict(id="r1", field="province", op="eq", value="Sindh",
                description="Applicant must be domiciled in Sindh",
                verification="verified", source_document_id="doc1",
                source_url="https://example.org/synthetic", source_passage="Sindh domicile required.",
                source_published=None, last_checked=date(2026, 10, 15), version="1",
                effective_from=None, effective_until=None, next_action="Confirm on the official page")
    base.update(kw)
    return Rule(**base)


def ev(r, **profile):
    return evaluate_rule(r, StudentProfile(**profile), TODAY)


class ConditionTests(unittest.TestCase):
    def test_eq_met_case_and_space_insensitive(self):
        self.assertEqual(ev(rule(), province=" sindh ").status, C.MET)

    def test_eq_not_met(self):
        self.assertEqual(ev(rule(), province="Punjab").status, C.NOT_MET)

    def test_in_met_and_not_met(self):
        r = rule(op="in", value=("Sindh", "Balochistan"))
        self.assertEqual(ev(r, province="balochistan").status, C.MET)
        self.assertEqual(ev(r, province="Punjab").status, C.NOT_MET)

    def test_gte_boundary(self):
        r = rule(field="marks_percent", op="gte", value=60)
        self.assertEqual(ev(r, marks_percent=60).status, C.MET)
        self.assertEqual(ev(r, marks_percent=59.99).status, C.NOT_MET)

    def test_lte_boundary(self):
        r = rule(field="monthly_family_income_pkr", op="lte", value=45000)
        self.assertEqual(ev(r, monthly_family_income_pkr=45000).status, C.MET)
        self.assertEqual(ev(r, monthly_family_income_pkr=45001).status, C.NOT_MET)

    def test_between_inclusive(self):
        r = rule(field="marks_percent", op="between", value=(50, 70))
        self.assertEqual(ev(r, marks_percent=50).status, C.MET)
        self.assertEqual(ev(r, marks_percent=70).status, C.MET)
        self.assertEqual(ev(r, marks_percent=70.1).status, C.NOT_MET)

    def test_missing_field_is_unknown_with_missing_info(self):
        res = ev(rule())
        self.assertEqual(res.status, C.UNKNOWN)
        self.assertEqual(res.missing_fields, ("province",))

    def test_blank_string_is_missing(self):
        self.assertEqual(ev(rule(), province="  ").status, C.UNKNOWN)

    def test_unverified_rule_never_not_met(self):
        res = ev(rule(verification="unverified"), province="Punjab")
        self.assertEqual(res.status, C.UNKNOWN)

    def test_conflicting_rule_is_unknown_with_ambiguity(self):
        res = ev(rule(verification="conflicting"), province="Sindh")
        self.assertEqual(res.status, C.UNKNOWN)
        self.assertTrue(res.ambiguity)

    def test_expired_rule_unknown(self):
        res = ev(rule(effective_until=date(2026, 10, 19)), province="Sindh")
        self.assertEqual(res.status, C.UNKNOWN)

    def test_not_yet_effective_unknown(self):
        res = ev(rule(effective_from=date(2026, 10, 21)), province="Sindh")
        self.assertEqual(res.status, C.UNKNOWN)

    def test_effective_on_boundary_days(self):
        r = rule(effective_from=TODAY, effective_until=TODAY)
        self.assertEqual(ev(r, province="Sindh").status, C.MET)

    def test_stale_source_unknown(self):
        res = ev(rule(last_checked=date(2026, 8, 1)), province="Sindh")
        self.assertEqual(res.status, C.UNKNOWN)

    def test_never_checked_unknown(self):
        self.assertEqual(ev(rule(last_checked=None), province="Sindh").status, C.UNKNOWN)

    def test_invalid_number_is_unknown_not_exception(self):
        r = rule(field="marks_percent", op="gte", value=60)
        self.assertEqual(ev(r, marks_percent="abc").status, C.UNKNOWN)

    def test_bool_not_accepted_as_number(self):
        r = rule(field="marks_percent", op="gte", value=0)
        self.assertEqual(ev(r, marks_percent=True).status, C.UNKNOWN)

    def test_nan_is_unknown(self):
        r = rule(field="marks_percent", op="gte", value=0)
        self.assertEqual(ev(r, marks_percent=float("nan")).status, C.UNKNOWN)

    def test_positive_infinity_is_unknown(self):
        r = rule(field="marks_percent", op="gte", value=0)
        self.assertEqual(ev(r, marks_percent=float("inf")).status, C.UNKNOWN)

    def test_negative_infinity_is_unknown(self):
        r = rule(field="marks_percent", op="gte", value=0)
        self.assertEqual(ev(r, marks_percent=float("-inf")).status, C.UNKNOWN)

    def test_result_carries_evidence_and_version(self):
        res = ev(rule(version="7"), province="Sindh")
        self.assertEqual((res.rule_id, res.rule_version, res.source_document_id), ("r1", "7", "doc1"))
        self.assertEqual(res.source_url, "https://example.org/synthetic")
        self.assertEqual(res.source_passage, "Sindh domicile required.")
        self.assertEqual(res.source_last_checked, date(2026, 10, 15))
        self.assertEqual(res.profile_value, "Sindh")

    def test_unknown_result_has_next_action(self):
        self.assertTrue(ev(rule()).next_action)


class RuleValidationTests(unittest.TestCase):
    def test_unknown_operator_rejected(self):
        with self.assertRaises(ValueError): rule(op="contains")

    def test_unknown_profile_field_rejected(self):
        with self.assertRaises(ValueError): rule(field="nonexistent")

    def test_numeric_op_needs_numeric_value(self):
        with self.assertRaises(ValueError): rule(field="marks_percent", op="gte", value="60")

    def test_between_needs_ordered_pair(self):
        with self.assertRaises(ValueError): rule(field="marks_percent", op="between", value=(70, 50))

    def test_in_needs_nonempty_collection(self):
        with self.assertRaises(ValueError): rule(op="in", value=())

    def test_bad_verification_value_rejected(self):
        with self.assertRaises(ValueError): rule(verification="probably")


class EvaluateAllTests(unittest.TestCase):
    def test_order_preserved(self):
        rules = [rule(id="a"), rule(id="b", field="marks_percent", op="gte", value=60)]
        out = evaluate_all(rules, StudentProfile(province="Sindh", marks_percent=70), TODAY)
        self.assertEqual([r.rule_id for r in out], ["a", "b"])


class OpportunityStatusTests(unittest.TestCase):
    def results(self, *statuses):
        return [evaluate_rule(
            rule(id=f"r{i}", verification="verified" if s != C.UNKNOWN else "unverified",
                 value="Sindh" if s == C.MET else "Punjab"),
            StudentProfile(province="Sindh"), TODAY) for i, s in enumerate(statuses)]

    def test_any_not_met_is_likely_not_eligible(self):
        self.assertEqual(derive_opportunity_status(self.results(C.MET, C.NOT_MET), True, False),
                         O.LIKELY_NOT_ELIGIBLE)

    def test_not_met_beats_unknown(self):
        self.assertEqual(derive_opportunity_status(self.results(C.UNKNOWN, C.NOT_MET), True, False),
                         O.LIKELY_NOT_ELIGIBLE)

    def test_unknown_needs_verification(self):
        self.assertEqual(derive_opportunity_status(self.results(C.MET, C.UNKNOWN), True, False),
                         O.NEEDS_VERIFICATION)

    def test_all_met_but_window_unconfirmed(self):
        self.assertEqual(derive_opportunity_status(self.results(C.MET), False, False),
                         O.APPLICATION_STATUS_UNCONFIRMED)

    def test_all_met_and_confirmed_open_is_potential_match(self):
        self.assertEqual(derive_opportunity_status(self.results(C.MET, C.MET), True, False),
                         O.POTENTIAL_MATCH)

    def test_closed_only_with_evidence(self):
        self.assertEqual(derive_opportunity_status(self.results(C.MET), False, True), O.CLOSED)
        self.assertNotEqual(derive_opportunity_status(self.results(C.MET), False, False), O.CLOSED)

    def test_empty_rules_needs_verification(self):
        self.assertEqual(derive_opportunity_status([], True, False), O.NEEDS_VERIFICATION)


if __name__ == "__main__":
    unittest.main()
