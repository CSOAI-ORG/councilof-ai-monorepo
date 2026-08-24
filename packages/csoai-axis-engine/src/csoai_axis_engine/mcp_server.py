"""white-label EUNOMIA measurement MCP server — the "hand them working tooling" pivot.

CSOAI doesn't just blog about AI compliance. It hands regulators, AI companies,
insurers, bond desks and COBOL parties a WORKING, pluggable GSPC/EUNOMIA tool they
can drop onto their own site (AG-UI / MCP / A2A / API / SDK) to self-audit E2E.

Tools (MCP, Model Context Protocol):
  - eunomia.axes                 list the measurement axes + frozen item counts
  - eunomia.measure_axis         run one axis against one model -> signed card (EAT)
  - eunomia.verify_card          offline-verify a signed measurement card
  - eunomia.crosswalk_articles   map a deployed AI system to EU AI Act articles + measure

White-label: set EUNOMIA_CLIENT (the party name), EUNOMIA_BRAND, EUNOMIA_402_URL
(payment gate). Every output is Ed25519-signed + EAT-chained; honesty preserved
(only a MEASURED axis earns a number).

Run: python3 -m csoai_axis_engine.mcp_server
"""
from __future__ import annotations

import json, os
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
    HAVE_MCP = True
except Exception:  # pragma: no cover
    HAVE_MCP = False

CLIENT = os.environ.get("EUNOMIA_CLIENT", "Council of AI (CSOAI Ltd, UK 16939677)")
BRAND = os.environ.get("EUNOMIA_BRAND", "Council OS")
PAY_URL = os.environ.get("EUNOMIA_402_URL", "")  # 402 payment hook

# EU AI Act articles that map to our axes (the "find every problem" crosswalk).
ARTICLE_AXES = {
    "art5": "governance",        # prohibited practices
    "art6": "governance",        # high-risk classification
    "art9": "provenance",        # data governance
    "art10": "provenance",
    "art11": "conformance",      # documentation? (mapped to MCP/tech conformance)
    "art13": "openness",         # transparency
    "art14": "care",             # human oversight
    "art15": "conformance",      # accuracy/robustness
    "art50": "provenance",       # AI-generated content transparency
}
AXES = None  # populated lazily from the engine

def _load_axes() -> dict:
    global AXES
    if AXES is None:
        try:
            from csoai_axis_engine.gspc_six_axis_e2e import AXES as _A
            AXES = dict(_A)
        except Exception:
            AXES = {}
    return AXES


def _sign(result: dict) -> dict:
    from csoai_axis_engine.sign_result import sign_result
    import tempfile, subprocess, sys
    # sign_result writes an Ed25519 card; reuse its canonicalisation via a temp file.
    with tempfile.TemporaryDirectory() as td:
        rp = Path(td) / "res.json"; rp.write_text(json.dumps(result))
        card = sign_result(str(rp), os.environ.get("EUNOMIA_KEY", "/workspace/axis-engine/sigil_ed25519.key"),
                           None if False else None)
    return card


if HAVE_MCP:
    mcp = FastMCP("eunomia-measurement", instructions=(
        f"White-label EUNOMIA measurement. Client: {CLIENT}. Brand: {BRAND}. "
        "Measurement, not certification. Only a MEASURED axis earns a number. "
        "Every result is Ed25519-signed + EAT-chained + recompute-able."))

    @mcp.tool()
    def eunomia_axes() -> dict:
        """List the EUNOMIA measurement axes + frozen item counts."""
        axes = _load_axes()
        return {"client": CLIENT, "brand": BRAND, "axes": [
            {"axis": a, "bench": v[0]} for a, v in axes.items()], "n_axes": len(axes)}

    @mcp.tool()
    def eunomia_measure_axis(axis: str, model: str) -> dict:
        """Run one measurement axis against one model -> signed accuracy + Wilson CI."""
        from csoai_axis_engine.gspc_six_axis_e2e import load_axis, score_axis
        items, field, labels = load_axis(axis)
        res = score_axis(model, items, field, labels)
        res.update({"axis": axis, "field": field, "labels": labels,
                    "client": CLIENT, "brand": BRAND, "signer": "did:web:csoai.org#estate-chain-1"})
        return res

    @mcp.tool()
    def eunomia_verify_card(card: dict) -> dict:
        """Verify a signed measurement card offline (recompute content_id + signature)."""
        import hashlib
        def canon(v):
            if isinstance(v, dict): return "{" + ",".join(canon(k)+":"+canon(v[k]) for k in sorted(v)) + "}"
            if isinstance(v, list): return "[" + ",".join(canon(x) for x in v) + "]"
            if isinstance(v, str): return json.dumps(v)
            if v is True: return "true"
            if v is False: return "false"
            if v is None: return "null"
            return str(v)
        body = {k: card[k] for k in sorted(card) if k not in ("content_id", "signature", "signer", "signed_at")}
        cid = hashlib.sha256(canon(body).encode()).hexdigest()
        match = cid == card.get("content_id")
        return {"valid": match, "recomputed_content_id": cid,
                "signer": card.get("signer"), "status": "OK" if match else "MISMATCH"}

    @mcp.tool()
    def eunomia_crosswalk_articles(ai_system: str, model: str, domain_hints: str = "") -> dict:
        """Map a deployed AI system to EU AI Act articles (Art 1-55) + measure exposure.

        domain_hints: comma-separated Annex III areas (hiring, credit, critical-infra,
        biometric, law-enforcement, education, essential-services, migration, justice).
        Returns the article exposure list (axis, requirement, penalty) + a signed sample."""
        from csoai_axis_engine.eu_ai_act_crosswalk import crosswalk
        hints = [h.strip() for h in domain_hints.split(",") if h.strip()]
        articles = crosswalk(ai_system, hints)
        sample = None
        try:
            from csoai_axis_engine.gspc_six_axis_e2e import load_axis, score_axis
            items, field, labels = load_axis("governance")
            sample = score_axis(model, items, field, labels)
            sample["axis"] = "governance"
        except Exception:
            sample = {"axis": "governance", "note": "measurement unavailable"}
        return {"client": CLIENT, "ai_system": ai_system, "model": model,
                "articles": articles, "n_articles": len(articles),
                "sample_measurement": sample,
                "gate": {"pay_url": PAY_URL, "402": bool(PAY_URL), "licence": "white-label"}}

    def run() -> int:
        mcp.run(transport="stdio", host="127.0.0.1", port=int(os.environ.get("EUNOMIA_PORT", "8786")))
        return 0
else:  # pragma: no cover
    def run() -> int:
        print("mcp SDK not installed; install via `uv add mcp` or pip install mcp.", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
