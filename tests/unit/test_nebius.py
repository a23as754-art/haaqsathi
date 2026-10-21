import io, json, unittest, urllib.error
import backend.models.nebius as n
from backend.models.nebius import (NebiusClient, ModelError, extract_content,
                                   parse_json_strict, validate_schema)

SCHEMA = {"required": ["a"], "properties": {"a": {"type": "string"}}}

class FakeResp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False

def opener_for(*bodies):
    it = iter(bodies)
    def _open(req, timeout=None):
        b = next(it)
        if isinstance(b, Exception): raise b
        return FakeResp(json.dumps(b).encode())
    return _open

def ok(text): return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 5}}
def client(*bodies): return NebiusClient(api_key="k", model="m", retries=1, opener=opener_for(*bodies))

class T(unittest.TestCase):
    def setUp(self): n.time.sleep = lambda s: None
    def test_empty_content_rejected(self):
        with self.assertRaises(ModelError): extract_content({"choices": [{"message": {"content": None}}]})
    def test_fenced_json_parsed(self):
        self.assertEqual(parse_json_strict('```json\n{"a":"x"}\n```'), {"a": "x"})
    def test_invalid_json_rejected(self):
        with self.assertRaises(ModelError): parse_json_strict("not json")
    def test_schema_missing_key(self):
        with self.assertRaises(ModelError): validate_schema({}, SCHEMA)
    def test_schema_wrong_type(self):
        with self.assertRaises(ModelError): validate_schema({"a": 1}, SCHEMA)
    def test_generate_happy_path_urdu(self):
        r = client(ok('{"a":"سندھ"}')).generate([{"role": "user", "content": "x"}], SCHEMA)
        self.assertEqual(r.parsed, {"a": "سندھ"})
    def test_retry_on_503_then_success(self):
        e = urllib.error.HTTPError("u", 503, "x", {}, None)
        self.assertEqual(client(e, ok("hi")).generate([]).content, "hi")
    def test_4xx_not_retried(self):
        e = urllib.error.HTTPError("u", 401, "x", {}, None)
        with self.assertRaises(ModelError): client(e, ok("hi")).generate([])
    def test_missing_key_config(self):
        with self.assertRaises(ModelError): NebiusClient(api_key="", model="m")

if __name__ == "__main__": unittest.main()
