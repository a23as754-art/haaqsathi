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
                        {"role": "user", "content": "\u0645\u06cc\u06ba \u06a9\u0631\u0627\u0686\u06cc\u060c \u0633\u0646\u062f\u06be \u0645\u06cc\u06ba \u0628\u06cc \u0627\u06cc\u0633 \u06a9\u06d2 \u062f\u0648\u0633\u0631\u06d2 \u0633\u0627\u0644 \u0645\u06cc\u06ba \u06c1\u0648\u06ba\u06d4"}],
                       SCHEMA, max_tokens=2048)
    except ModelError as e:
        print("FAIL:", e); return 1
    print("model:", c.model); print("latency_s: %.2f" % r.latency_s)
    fields = r.parsed or {}
    if not all(str(fields.get(k, "")).strip() for k in ("education_level", "province", "language")):
        print("FAIL: one or more extracted fields are empty"); return 1
    province = str(fields["province"]).strip().casefold()
    if province not in ("sindh", "\u0633\u0646\u062f\u06be"):
        print("FAIL: unexpected province:", fields["province"]); return 1
    print("usage:", r.usage); print("parsed:", json.dumps(r.parsed, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
