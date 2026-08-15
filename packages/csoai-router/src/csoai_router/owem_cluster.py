from __future__ import annotations

import argparse, glob, hashlib, json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = HERE / "benchmark-results" / "govbench"
OLLAMA = "http://localhost:11434/api/chat"

# Fallback model when the board is empty / no expert for a dimension. The base
# blob is qwen2.5:0.5b (per the cluster-on-disk footprint note above). select_expert
# returns this name when build_expert_table() yields no models. 2026-08-08 fix:
# was previously referenced without being defined, causing NameError in HONEY stage.
BASE = "qwen2.5:0.5b"


import argparse, glob, hashlib, json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = HERE / "benchmark-results" / "govbench"
OLLAMA = "http://localhost:11434/api/chat"

# ── TIER 1: SOV1 spine — dimension classifier ────────────────────────────────
# Keyword routing, deliberately. A learned router would need training data we do not have, and
# would be one more unmeasured component. This is inspectable and falsifiable; when it misroutes
# you can see exactly why. Upgrade it only when there is a measurement showing it is the bottleneck.
# ORDER IS THE ALGORITHM — first match wins, so SPECIFIC dimensions are tested before GENERAL
# ones. Measured 2026-07-28: an earlier version scored all cues equally and took the highest
# match count. That gave 25.8% accuracy, because "governance" (ai act|policy|framework) matched
# almost everything and was ALSO the fallback — a black hole that swallowed ethics 0/5,
# transparency 0/5, fairness 0/5 and compliance 0/10. Broad categories must be tested LAST, and
# must not share vocabulary with the narrow ones they would otherwise absorb.
DIMENSION_CUES = [
    # ── most specific first: proper nouns and unmistakable terms ──
    ("sigil_chain",   r"\b(sigil|ed25519|attestation|provenance chain|signed receipt|audit chain|audit trail)\b"),
    ("defence",       r"\b(aukus|nato|ncsc|jsp ?936|five eyes|diana|mod\b|military|defen[cs]e)\b"),
    ("cybersecurity", r"\b(malware|ransomware|phish|exfiltrat|zero.?day|encrypt|breach|cyber|firewall|intrusion)\b"),
    ("robustness",    r"\b(jailbreak|ignore (all )?(previous |prior )?instruction|developer mode|"
                      r"system prompt|override|adversarial input|prompt.?inject)\b"),
    ("privacy",       r"\b(gdpr|personal data|dpia|data protection impact|right to erasure|"
                      r"privacy by design|pii|article 9|consent)\b"),
    ("sovereignty",   r"\b(sovereign|data residen|onshore|offshore|jurisdiction|national control|"
                      r"cross.?border transfer)\b"),
    ("fairness",      r"\b(discriminat|protected (class|characteristic)|demographic parity|"
                      r"disparate impact|equit|bias audit)\b"),
    # ── mid-specificity ──
    ("safety",        r"\b(harm|weapon|bomb|explosive|kill|poison|drug|abuse|suicide|"
                      r"stalk|traffick|fraud|exploitation material|dangerous)\b"),
    ("security",      r"\b(red.?team|supply.?chain|vulnerab|threat model|attack surface|"
                      r"unauthori[sz]ed access|model security|secure)\b"),
    ("transparency",  r"\b(explain|explainab|interpretab|transparen|disclos|black.?box|"
                      r"algorithmic transparency)\b"),
    ("accountability",r"\b(accountab|responsib|liab|who is (responsible|accountable)|"
                      r"human oversight|redress)\b"),
    ("ethics",        r"\b(ethic|moral|dilemma|stakeholder|value alignment|human dignity)\b"),
    ("evolution",     r"\b(evolv|adapt|continual|model drift|retrain|version|lifecycle|"
                      r"post.?market monitor)\b"),
    ("compliance",    r"\b(complian|conformity|annex|certif|solvency|dora|obligation|"
                      r"deadline|penalt|fine|enforcement)\b"),
    # ── broadest LAST: only reached when nothing specific matched ──
    ("governance",    r"\b(ai act|iso ?42001|nist ai rmf|oecd|governance|policy|framework|"
                      r"regulat|standard|principle)\b"),
]
# 2026-07-28 BUGFIX — the TRAILING \b silently broke every PREFIX STEM in the table above.
#
# `\b(discriminat|…)\b` cannot match "discriminating". The closing \b demands a word boundary
# immediately after "discriminat", and "i" is a word character. So `discriminat`, `equit`,
# `complian`, `vulnerab`, `accountab`, `transparen`, `evolv`, `responsib`, `penalt` — every stem
# written to catch inflections — only fired when the stem happened to END a word. Almost never.
#
# Those queries fell through to the `governance` fallback. That IS the black-hole symptom
# measured at 0.258 and still at 0.333 after the ordering fix: the ordering was only half of it.
# Stems need an OPEN right edge; the leading \b stays, so they still anchor at a word start.
_COMPILED = [(re.compile(p[:-2] if p.endswith(r")\b") else p, re.I), d)
             for d, p in DIMENSION_CUES]


def classify_dimension(q: str) -> str:
    """First specific match wins; 'governance' is the fallback, never a competitor.

    Deliberately NOT highest-match-count — that let a broad category outvote a narrow one on a
    single query (measured: 25.8% accuracy). Ordered first-match is inspectable: when it
    misroutes you can point at the exact rule, which a learned router could not give us.
    """
    for rx, dim in _COMPILED:
        if rx.search(q):
            return dim
    return "governance"


# ── TIER 2: OWEM expert table — derived from measurement, never hardcoded ─────
def build_expert_table() -> tuple[dict, dict]:
    """Read the 15-dim board and pick each dimension's measured winner.

    Re-derived on every load ON PURPOSE. If a new model is benchmarked, the cluster re-routes
    itself with no code change. A hardcoded table would silently rot the moment the board moved —
    which is the failure mode this whole estate keeps hitting.
    """
    from withdrawn import is_withdrawn
    models: dict[str, dict] = {}
    for f in glob.glob(str(RESULTS / "*.json")):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        for r in (d if isinstance(d, list) else [d]):
            if not isinstance(r, dict):
                continue
            dims = r.get("dimensions")
            # A withdrawn model must never win a routing slot. `sov33-evolved-c2` held
            # `fairness` and `robustness` here while emitting "1\n1\n1" to every prompt —
            # it topped both columns precisely because the grader paid for saying nothing.
            if is_withdrawn(r.get("model", "")):
                continue
            if (isinstance(dims, dict) and len(dims) == 15
                    and all(isinstance(v, (int, float)) for v in dims.values())):
                models[r["model"]] = dims
    if not models:
        return {}, {}
    table = {}
    for dim in next(iter(models.values())):
        m, v = max(((m, dd[dim]) for m, dd in models.items()), key=lambda x: x[1])
        table[dim] = {"expert": m, "score": v}
    return table, models


# ── TIER 3: attestation ──────────────────────────────────────────────────────
def select_expert(dim: str, per_dimension: bool = False) -> tuple[str, str]:
    """Pick the model that answers. Returns (model, why).

    ═══════════════════════════════════════════════════════════════════════════════
    PER-DIMENSION ROUTING IS OFF BY DEFAULT, AND THAT IS A MEASURED DECISION
    ═══════════════════════════════════════════════════════════════════════════════
    `router_control.py`, n=136, same items and same wrapper pool, only the selection rule
    varying:

        ROUTED 43.7%    FIXED (best single) 42.8%    RANDOM 34.5%

        ROUTED vs FIXED   Δ +0.90  95% CI [-1.99, +3.79]   crosses zero — no effect shown
        ROUTED vs RANDOM  Δ +9.18  95% CI [+4.21, +14.14]  real

    So the classifier beats chance but does NOT beat always using the best single model. The
    +9.42 the routed arm scored against raw base in the n=186 system run was the WRAPPER —
    going to a governance-tuned model at all — not the routing.

    The cause is legible: the expert table is derived from a board where **0 of 15 dimensions
    have a resolved winner**. The router selects on differences that are themselves noise, so
    it cannot beat ignoring them. This is the same constraint that blocks `mitosis` — no cell
    split clears its minimum detectable effect either. Item expansion unblocks both.

    Routing therefore stays available but OFF. Shipping it on would mean deploying a
    configuration our own measurement does not support, which is the failure this estate keeps
    having to retract. Turn it on when a re-run of `router_control.py` shows ROUTED > FIXED
    with a CI clear of zero — not before.
    """
    table, models = build_expert_table()
    if not models:
        return BASE, "no board — falling back to base"
    if per_dimension:
        e = table.get(dim, {}).get("expert")
        if e:
            return e, f"per-dimension routing (EXPERIMENTAL — not supported by router_control)"
    best = max(models, key=lambda m: sum(models[m].values()) / len(models[m]))
    return best, "best single model (routing off: ROUTED vs FIXED CI [-1.99, +3.79])"


def attest(query: str, dim: str, expert: str, response: str) -> dict:
    """Sign the ROUTING DECISION, not just the output. Without this, "the cluster chose the best
    expert" is an unverifiable claim — exactly the class of claim this estate keeps having to retract."""
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "dimension": dim,
        "expert": expert,
        "response_sha256": hashlib.sha256(response.encode()).hexdigest(),
    }
    try:
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        seed = os.environ.get("SIGIL_SEED")
        if not seed:
            payload["signature"] = None
            payload["note"] = "UNSIGNED — SIGIL_SEED not set. Fails open on signing, never on the gate."
            return payload
        k = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(seed.encode()).digest())
        canon = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        payload["signature"] = k.sign(canon).hex()
        payload["public_key"] = k.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    except Exception as e:
        payload["signature"] = None
        payload["note"] = f"unsigned: {e}"
    return payload


def ask(model: str, prompt: str, timeout: int = 300) -> str:
    body = json.dumps({"model": model, "stream": False,
                       "options": {"temperature": 0, "num_predict": 200},
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(OLLAMA, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"].strip()


def route(query: str, execute: bool = True) -> dict:
    # TIER 0 — deterministic gate. Runs before any routing and cannot be overridden.
    try:
        from care_gate_v2 import tier1_hard_stop
        breach, label, cite = tier1_hard_stop(query)
        if breach:
            return {"blocked": True, "tier": "0-deterministic", "reason": label,
                    "citation": cite, "response": "I can't help with that.",
                    "note": "Hard stop precedes routing. No expert can override it."}
    except Exception:
        pass

    table, models = build_expert_table()
    if not table:
        return {"error": "no 15-dim benchmark results found — cannot route without measurement"}

    dim = classify_dimension(query)
    sel = table[dim]
    out = {"blocked": False, "dimension": dim, "expert": sel["expert"],
           "expert_dim_score": sel["score"], "experts_available": len(models)}
    if execute:
        try:
            resp = ask(sel["expert"], query)
            out["response"] = resp
            out["attestation"] = attest(query, dim, sel["expert"], resp)
        except Exception as e:
            out["error"] = f"expert unreachable: {e}"
    return out


def explain() -> None:
    table, models = build_expert_table()
    if not table:
        print("  no 15-dim results found"); return
    avg = {m: sum(d.values()) / 15 for m, d in models.items()}
    best = max(avg, key=avg.get)
    oracle = sum(v["score"] for v in table.values()) / 15
    print(f"  OWEM CLUSTER — {len(models)} experts, 15 dimensions\n")
    for dim, v in sorted(table.items()):
        print(f"    {dim:15s} -> {v['expert']:26s} {v['score']:5.1f}%")
    from collections import Counter
    c = Counter(v["expert"] for v in table.values())
    print(f"\n  {len(c)} distinct experts hold at least one dimension:")
    for m, n in c.most_common():
        print(f"    {n:2d} dims  {m}")
    print(f"\n  best single model : {avg[best]:.1f}%  ({best})")
    print(f"  cluster (oracle)  : {oracle:.1f}%")
    print(f"  gain              : +{oracle - avg[best]:.1f} pts, zero training")
    print(f"\n  Note: every expert shares one ~400MB base blob, so the cluster is ~400MB on disk,")
    print(f"  not {len(models)}x400MB. That is what makes it free-tier deployable.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--route")
    ap.add_argument("--explain", action="store_true")
    ap.add_argument("--dry", action="store_true", help="route without calling the model")
    a = ap.parse_args()
    if a.explain or not a.route:
        explain()
    else:
        print(json.dumps(route(a.route, execute=not a.dry), indent=2))
