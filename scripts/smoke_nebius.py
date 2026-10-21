"""Phase 1 smoke test: one real call to an NVIDIA model on Nebius Token Factory.
Run:  NEBIUS_API_KEY=... NEBIUS_MODEL=nvidia/... python scripts/smoke_nebius.py
"""
import json, sys
sys.path.insert(0, ".")
from backend.models.nebius import NebiusClient, ModelError

SCHEMA = {"type": "object", "required": ["education_level", "province", "language"],
          "properties": {"education_level": {"type": "string"}, "province": {"type": "string"},
                         "language": {"type": "string"}}}

def main() -> int:
    try:
        c = NebiusClient()
        r = c.generate([{"role": "system", "content": "Extract fields. Reply with JSON only."},
                        {"role": "user", "content": "میں کراچی، سندھ میں بی ایس کے دوسرے سال میں ہوں۔"}],
                       SCHEMA, max_tokens=2048)
    except ModelError as e:
        print("FAIL:", e); return 1
    print("model:", c.model); print("latency_s: %.2f" % r.latency_s)
    print("usage:", r.usage); print("parsed:", json.dumps(r.parsed, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
