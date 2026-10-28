import re, unittest
from datetime import date
from pathlib import Path

try:
    from fastapi.testclient import TestClient
    from backend.api.app import create_app
    HAVE = True
except Exception:  # pragma: no cover
    HAVE = False

WEB = Path(__file__).resolve().parents[2] / "web"


class WebSourceGuards(unittest.TestCase):
    """Plain file checks: these run without fastapi."""
    def test_no_dangerous_dom_apis(self):
        for f in WEB.glob("*.js"):
            src = f.read_text(encoding="utf-8")
            for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
                self.assertNotIn(bad, src, f"{f.name} uses {bad}")

    def test_no_browser_storage_or_third_party_urls(self):
        for f in list(WEB.glob("*.js")) + [WEB / "index.html", WEB / "styles.css"]:
            src = f.read_text(encoding="utf-8")
            self.assertNotIn("localStorage", src); self.assertNotIn("sessionStorage", src)
            self.assertIsNone(re.search(r"https?://(?!www\.w3\.org)", src), f"external URL in {f.name}")

    def test_index_has_strict_csp_and_viewport(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", html); self.assertIn("script-src 'self'", html)
        self.assertNotIn("unsafe-inline", html); self.assertIn("width=device-width", html)

    def test_rtl_is_switched_by_language(self):
        self.assertIn('"rtl"', (WEB / "app.js").read_text(encoding="utf-8"))


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class WebServingTests(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(create_app(today_fn=lambda: date(2026, 10, 21)))

    def test_index_and_js_served(self):
        r = self.c.get("/"); self.assertEqual(r.status_code, 200); self.assertIn('id="app"', r.text)
        self.assertEqual(self.c.get("/app.js").status_code, 200)

    def test_api_not_shadowed_by_static_mount(self):
        self.assertEqual(self.c.get("/api/health").json()["status"], "ok")

    def test_repo_files_not_exposed(self):
        for path in ("/package.json", "/../README.md", "/data/fixtures/catalog.json", "/.env"):
            self.assertEqual(self.c.get(path).status_code, 404, path)


if __name__ == "__main__":
    unittest.main()
