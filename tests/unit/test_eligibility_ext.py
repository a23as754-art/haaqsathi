import unittest
from datetime import date

from backend.eligibility.models import ConditionStatus as C, StudentProfile
from backend.eligibility.engine import evaluate_rule
from tests.unit.test_eligibility import rule, TODAY


def ev(r, **p):
    return evaluate_rule(r, StudentProfile(**p), TODAY)


def any_rule(**kw):
    return rule(field="*", op="any_of",
                value=(("marks_percent", "gte", 60), ("cgpa", "gte", 2.5)), **kw)


class NeAndBoolTests(unittest.TestCase):
    def test_ne(self):
        r = rule(field="admission_basis", op="ne", value="self_finance")
        self.assertEqual(ev(r, admission_basis="open_merit").status, C.MET)
        self.assertEqual(ev(r, admission_basis=" Self_Finance ").status, C.NOT_MET)
        self.assertEqual(ev(r).status, C.UNKNOWN)

    def test_bool_eq(self):
        r = rule(field="receives_other_scholarship", op="eq", value=False)
        self.assertEqual(ev(r, receives_other_scholarship=False).status, C.MET)
        self.assertEqual(ev(r, receives_other_scholarship=True).status, C.NOT_MET)
        self.assertEqual(ev(r).status, C.UNKNOWN)


class AnyOfTests(unittest.TestCase):
    def test_met_by_marks(self):
        self.assertEqual(ev(any_rule(), marks_percent=65).status, C.MET)

    def test_met_by_cgpa_only(self):
        self.assertEqual(ev(any_rule(), cgpa=3.0).status, C.MET)

    def test_met_even_if_other_branch_missing(self):
        self.assertEqual(ev(any_rule(), marks_percent=65).status, C.MET)

    def test_not_met_only_when_all_branches_fail(self):
        self.assertEqual(ev(any_rule(), marks_percent=50, cgpa=2.0).status, C.NOT_MET)

    def test_unknown_when_a_branch_is_missing_and_none_met(self):
        res = ev(any_rule(), marks_percent=50)
        self.assertEqual(res.status, C.UNKNOWN)
        self.assertEqual(res.missing_fields, ("cgpa",))

    def test_unknown_when_nothing_given(self):
        res = ev(any_rule())
        self.assertEqual(res.status, C.UNKNOWN)
        self.assertEqual(set(res.missing_fields), {"marks_percent", "cgpa"})

    def test_untrusted_any_of_is_unknown(self):
        self.assertEqual(ev(any_rule(verification="unverified"), marks_percent=10, cgpa=1).status, C.UNKNOWN)

    def test_validation(self):
        with self.assertRaises(ValueError): rule(field="marks_percent", op="any_of", value=(("marks_percent", "gte", 1), ("cgpa", "gte", 1)))
        with self.assertRaises(ValueError): rule(field="*", op="any_of", value=(("marks_percent", "gte", 60),))
        with self.assertRaises(ValueError): rule(field="*", op="any_of", value=(("marks_percent", "gte", 60), ("cgpa", "contains", 2)))
        with self.assertRaises(ValueError): rule(field="*", op="any_of", value=(("marks_percent", "gte", 60), ("nope", "gte", 2)))


class AmbiguityTests(unittest.TestCase):
    def test_rule_ambiguity_passes_to_result(self):
        res = ev(rule(ambiguity="Source page is undated."), province="Sindh")
        self.assertEqual(res.status, C.MET)
        self.assertEqual(res.ambiguity, "Source page is undated.")


if __name__ == "__main__":
    unittest.main()
