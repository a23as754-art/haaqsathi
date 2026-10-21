"""API tests. Skipped automatically when fastapi/httpx are not installed (they run on your machine)."""
import unittest
from datetime import date

try:
    from fastapi.testclient import TestClient
    from backend.api.app import create_app
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

STUDENT = {"education_level": "undergraduate", "institution_sector": "public", "admission_basis": "open_merit"}


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(create_app(today_fn=lambda: date(2026, 10, 21)))

    def test_health(self):
        r = self.c.get("/api/health"); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_search_orders_and_has_disclaimer_and_no_score(self):
        r = self.c.post("/api/opportunities/search", json={"profile": STUDENT}); self.assertEqual(r.status_code, 200)
        j = r.json()
        self.assertEqual([x["status"] for x in j["results"]], ["needs_verification", "likely_not_eligible"])
        self.assertIn("not an award decision", j["disclaimer"])
        self.assertNotIn("match_percent", r.text)
        self.assertFalse(j["results"][0]["application"]["confirmed_open"])

    def test_explain_returns_evidence(self):
        r = self.c.post("/api/matches/hec-nbs/explain", json={"profile": STUDENT}); self.assertEqual(r.status_code, 200)
        e = r.json()["entries"][0]
        self.assertTrue(e["source_url"].startswith("https://")); self.assertEqual(e["status"], "met")

    def test_explain_unknown_program_404(self):
        self.assertEqual(self.c.post("/api/matches/nope/explain", json={"profile": STUDENT}).status_code, 404)

    def test_checklist(self):
        r = self.c.post("/api/checklists/generate", json={"profile": STUDENT, "program_id": "hec-nbs"})
        self.assertEqual(r.status_code, 200); self.assertTrue(r.json()["items"])

    def test_sensitive_field_refused_and_not_echoed(self):
        r = self.c.post("/api/profile", json={"profile": {"cnic": "12345-1234567-1"}})
        self.assertEqual(r.status_code, 422); self.assertNotIn("12345", r.text)

    def test_invalid_vocab_422(self):
        self.assertEqual(self.c.post("/api/profile", json={"profile": {"education_level": "wizard"}}).status_code, 422)

    def test_source_endpoint(self):
        r = self.c.get("/api/sources/hec-nbs-faq"); self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["tier"], "A")
        self.assertEqual(self.c.get("/api/sources/nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
