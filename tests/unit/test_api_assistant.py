"""Skipped automatically when fastapi/httpx are missing."""
import unittest
from datetime import date

try:
    from fastapi.testclient import TestClient
    from backend.api.app import create_app
    from backend.models.nebius import ModelError
    from tests.unit.test_agents import FakeClient
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

TODAY = lambda: date(2026, 10, 21)


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class AssistantApiTests(unittest.TestCase):
    def test_503_when_no_model_configured(self):
        c = TestClient(create_app(today_fn=TODAY))
        self.assertEqual(c.post("/api/assistant/message", json={"message": "hi"}).status_code, 503)

    def test_message_flow_with_fake_client(self):
        c = TestClient(create_app(today_fn=TODAY, model_client=FakeClient({"education_level": "undergraduate"})))
        r = c.post("/api/assistant/message", json={"message": "I am an undergraduate"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["questions"]); self.assertIn("not an award decision", r.json()["disclaimer"])

    def test_502_on_model_failure_without_details(self):
        c = TestClient(create_app(today_fn=TODAY, model_client=FakeClient(error=ModelError("HTTP 500 secret-detail"))))
        r = c.post("/api/assistant/message", json={"message": "hi"})
        self.assertEqual(r.status_code, 502); self.assertNotIn("secret-detail", r.text)

    def test_message_length_limit(self):
        c = TestClient(create_app(today_fn=TODAY, model_client=FakeClient({})))
        self.assertEqual(c.post("/api/assistant/message", json={"message": "x" * 2001}).status_code, 422)

    def test_narrative_without_model_is_labelled_template(self):
        c = TestClient(create_app(today_fn=TODAY))
        r = c.post("/api/matches/hec-nbs/narrative", json={"profile": {"education_level": "undergraduate"}, "language": "ur"})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.json()["generated_by"], "template")


if __name__ == "__main__":
    unittest.main()
