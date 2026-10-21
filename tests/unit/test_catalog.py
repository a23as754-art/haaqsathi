import copy, json, unittest
from pathlib import Path

from backend.catalog.loader import load_catalog, CatalogError

FIXTURE = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "catalog.json"


def raw():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class RealCatalogTests(unittest.TestCase):
    def test_loads(self):
        cat = load_catalog(FIXTURE)
        self.assertGreaterEqual(len(cat.programs), 2)

    def test_verified_rules_cite_official_sources_only(self):
        cat = load_catalog(FIXTURE)
        for p in cat.programs:
            for r in p.rules:
                if r.verification == "verified":
                    self.assertIn(cat.sources[r.source_document_id].tier, ("A", "B"))

    def test_no_fabricated_deadlines_or_open_claims(self):
        for p in load_catalog(FIXTURE).programs:
            self.assertIsNone(p.application_deadline)
            self.assertFalse(p.application_confirmed_open)
            self.assertFalse(p.closure_evidenced)

    def test_every_source_is_https_with_check_date(self):
        for s in load_catalog(FIXTURE).sources.values():
            self.assertTrue(s.url.startswith("https://"))
            self.assertIsNotNone(s.last_checked)


class LoaderPolicyTests(unittest.TestCase):
    def test_verified_rule_cannot_cite_tier_c(self):
        d = raw()
        sid = d["programs"][0]["rules"][0]["source_id"]
        d["sources"][sid]["tier"] = "C"
        with self.assertRaises(CatalogError): load_catalog(d)

    def test_missing_source_rejected(self):
        d = raw(); d["programs"][0]["rules"][0]["source_id"] = "nope"
        with self.assertRaises(CatalogError): load_catalog(d)

    def test_duplicate_rule_id_rejected(self):
        d = raw(); rs = d["programs"][0]["rules"]; rs.append(copy.deepcopy(rs[0]))
        with self.assertRaises(CatalogError): load_catalog(d)

    def test_bad_date_rejected(self):
        d = raw(); next(iter(d["sources"].values()))["last_checked"] = "20-10-2026"
        with self.assertRaises(CatalogError): load_catalog(d)

    def test_invalid_rule_rejected_as_catalog_error(self):
        d = raw(); d["programs"][0]["rules"][0]["op"] = "contains"
        with self.assertRaises(CatalogError): load_catalog(d)


if __name__ == "__main__":
    unittest.main()
