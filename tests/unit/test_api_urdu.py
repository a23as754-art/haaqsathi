"""Skipped automatically when fastapi/httpx are not installed."""
import re, unittest
from datetime import date

try:
    from fastapi.testclient import TestClient
    from backend.api.app import create_app
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

URDU = re.compile(r"[\u0600-\u06ff]")
STUDENT = {"education_level": "undergraduate", "institution_sector": "public", "admission_basis": "open_merit"}


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class UrduApiTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(create_app(today_fn=lambda: date(2026, 10, 21)))

    def test_explain_urdu_text_and_english_default(self):
        ur = self.c.post("/api/matches/hec-nbs/explain", json={"profile": STUDENT, "language": "ur"}).json()["entries"]
        for e in ur:
            self.assertTrue(URDU.search(e["text"]["requirement"]) and URDU.search(e["text"]["reason"]), e["rule_id"])
        en = self.c.post("/api/matches/hec-nbs/explain", json={"profile": STUDENT}).json()["entries"]
        self.assertEqual(en[0]["text"]["language"], "en")
        self.assertEqual(en[0]["requirement"], ur[0]["requirement"])        # raw English fields unchanged

    def test_checklist_urdu(self):
        items = self.c.post("/api/checklists/generate", json={"profile": STUDENT, "program_id": "hec-nbs", "language": "ur"}).json()["items"]
        self.assertTrue(items and all(URDU.search(i["text"]) for i in items))

    def test_search_note_localized(self):
        r = self.c.post("/api/opportunities/search", json={"profile": STUDENT, "language": "ur"}).json()["results"]
        self.assertTrue(all(URDU.search(x["application"]["note"]) for x in r))


if __name__ == "__main__":
    unittest.main()
