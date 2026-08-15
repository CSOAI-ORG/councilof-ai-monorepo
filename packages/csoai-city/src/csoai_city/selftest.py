"""Gate self-test — run this before trusting any city board.

Every one of the eight Article 5 prohibitions gets a positive probe (must BLOCK
and cite the right subparagraph) and the near-miss gets a negative probe (must
ALLOW). A gate that blocks everything is as useless as one that blocks nothing,
so both directions are checked.

Then the chain is exercised end to end: append, tamper, verify. A tampered chain
MUST report broken — a verifier that cannot fail is not a verifier.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .chain import Chain
from .law import ALLOWED, BLOCKED, UNMEASURED, gate

# (name, action json, expected verdict, expected citation or None)
PROBES: List[tuple] = [
    ("5a-positive", {"act": "persuade", "means": ["subliminal"], "harm": True}, BLOCKED, "Art 5(1)(a)"),
    ("5a-negative", {"act": "persuade", "means": ["argument"], "harm": False}, ALLOWED, None),
    ("5b-positive", {"act": "persuade", "traits": ["disability"], "harm": True}, BLOCKED, "Art 5(1)(b)"),
    ("5b-negative", {"act": "persuade", "traits": ["hobby"], "harm": False}, ALLOWED, None),
    ("5c-positive", {"act": "score", "context": "civic", "harm": True}, BLOCKED, "Art 5(1)(c)"),
    ("5c-negative", {"act": "score", "context": "contract" and "market", "harm": False}, ALLOWED, None),
    ("5d-positive", {"act": "predict_offence", "solely_profiling": True}, BLOCKED, "Art 5(1)(d)"),
    ("5d-negative", {"act": "predict_offence", "solely_profiling": False}, ALLOWED, None),
    ("5e-positive", {"act": "scrape", "means": ["untargeted"]}, BLOCKED, "Art 5(1)(e)"),
    ("5e-negative", {"act": "scrape", "means": ["consented"]}, ALLOWED, None),
    ("5f-positive", {"act": "infer_emotion", "context": "workplace"}, BLOCKED, "Art 5(1)(f)"),
    ("5f-negative", {"act": "infer_emotion", "context": "medical"}, ALLOWED, None),
    ("5g-positive", {"act": "categorise", "traits": ["religion"]}, BLOCKED, "Art 5(1)(g)"),
    ("5g-negative", {"act": "categorise", "traits": ["shoe_size"]}, ALLOWED, None),
    ("5h-positive", {"act": "identify", "realtime": True, "context": "public_space"}, BLOCKED, "Art 5(1)(h)"),
    ("5h-negative", {"act": "identify", "realtime": False, "context": "public_space"}, ALLOWED, None),
    # the third verdict must be reachable
    ("unparseable", "I refuse to answer in JSON.", UNMEASURED, None),
    ("empty", "", UNMEASURED, None),
    ("bad-act", {"act": "teleport"}, UNMEASURED, None),
]


def run() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    for name, probe, want, want_cite in PROBES:
        raw = probe if isinstance(probe, str) else json.dumps(probe)
        v = gate(raw, source="self-test:city")
        ok = v.verdict == want and (want_cite is None or want_cite in v.citations)
        results.append({"probe": name, "want": want, "got": v.verdict,
                        "citations": v.citations, "ok": ok})

    gate_ok = all(r["ok"] for r in results)

    # chain: append two, verify intact, tamper, verify broken
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "chain.jsonl"
        ch = Chain(p, key_path=Path(td) / "key")
        ch.append(1, {"kind": "self-test", "n": 1})
        ch.append(2, {"kind": "self-test", "n": 2})
        intact = ch.verify()
        lines = p.read_text().splitlines()
        rec = json.loads(lines[0]); rec["body"]["n"] = 99
        lines[0] = json.dumps(rec)
        p.write_text("\n".join(lines) + "\n")
        tampered = Chain(p, key_path=Path(td) / "key").verify()

    chain_ok = bool(intact["chain_intact"]) and not tampered["chain_intact"]

    return {
        "ok": gate_ok and chain_ok,
        "gate_ok": gate_ok,
        "gate_probes": results,
        "gate_failures": [r for r in results if not r["ok"]],
        "chain_ok": chain_ok,
        "chain_intact_when_clean": intact,
        "chain_detects_tampering": not tampered["chain_intact"],
        "note": "A gate that cannot fail, and a verifier that cannot fail, are both worthless. "
                "Both directions are tested here.",
    }


if __name__ == "__main__":
    r = run()
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["ok"] else 1)
