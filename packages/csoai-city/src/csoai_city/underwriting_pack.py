"""csoai-city.underwriting_pack — Diamond-3: the underwriting-INPUT demo pack.

The catapult mission for Diamond 3: hand an AI-liability underwriter (Munich Re
aiSure, Armilla at Lloyd's, an AIUC-1-style underwriting team) EXACTLY what a
measured, signed, governance score looks like when it is used as an underwriting
INPUT. We sell the SCORE, not insurance.

The pack is deliberately honest about its own limits:
  * COMPOSITE ONLY over MEASURED axes — an unmeasured axis is NEVER counted as a
    silent 0.0 (that would quietly drag the score down without evidence). If an
    axis is unmeasured it is listed with source='unmeasured' and excluded from
    the composite, and the pack records how many axes were excluded.
  * PRECISION-WEIGHTED mean via attestation_registry.from_accuracy — axes with
    more evidence (higher n -> smaller sigma -> higher precision) weigh more.
    This is the estate's deterministic wiring, no model judges this.
  * DISCLAIMER BUILT IN — the pack is a measurement INPUT for underwriting
    pricing, NOT a policy, quote, certification, or legal advice.
  * SIGNED ENVELOPE via cose_wrapper.wrap — the whole pack is wrapped in a
    csoai-cose-sign1 Ed25519 envelope a third party can verify without us.
  * Reference prices are REFERENCES (strings describing how a real underwriter
    prices off such a score), not quotes we issue.

Deterministic: same inputs -> byte-identical axes list, identical composite.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from . import attestation_registry as _ar
    from .cose_wrapper import wrap as _cose_wrap
    from .cose_wrapper import verify as _cose_verify
    _HAS_WIRING = True
except Exception:  # pragma: no cover
    _HAS_WIRING = False

# The disclaimer is a hard invariant — every underwriting pack carries it.
DISCLAIMER = (
    "measurement input for underwriting pricing — NOT a policy, quote, "
    "certification, or legal advice"
)

# Reference prices: how REAL underwriters price off a measured governance score.
# These are descriptions of the channel/pricing basis, NOT quotes we issue.
DEFAULT_REFERENCE_PRICES = {
    "munich_re_aisure": "priced off AIUC-1 audit score, coverage up to EUR 100M per event",
    "armilla": "Lloyd's coverholder — full-stack underwriting on AI/tech E&O, priced per measured axis",
    "aiuc1": "AI underwriting credit — audit-grade score gates binding vs non-binding cover",
}

# Default key path (macOS-friendly, overridable). Wrap generates on first use.
from .keystone import DEFAULT_KEY_PATH  # ONE canonical key path (ADR_ONE_SIGNER) — was ~/.sovos, now unified


def _today() -> str:
    """Deterministic assessed_at. Defaults to UTC now if caller passes none."""
    return datetime.now(timezone.utc).isoformat()


def build_underwriting_input(
    entity: str,
    model_scores: Dict[str, float],
    n_per_axis: Dict[str, int],
    reference_prices: Optional[Dict[str, str]] = None,
    assessed_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a deterministic underwriting-INPUT record.

    Args:
        entity: the name/ID of the AI system being assessed.
        model_scores: axis -> score in [0,1] (the best-model accuracy from a
            GSPC board, OR any measured score). An axis present here is measured.
        n_per_axis: axis -> number of graded items (evidence count). Required
            for every measured axis; drives precision (sigma).
        reference_prices: optional {channel: how it prices} map. Defaults to the
            real Munich Re / Armilla / AIUC-1 references.
        assessed_at: optional ISO timestamp; defaults to UTC now (non-deterministic
            only when omitted — pass a fixed value for deterministic tests).

    Returns a dict:
        {entity, assessed_at, axes:[...], composite, n_axes, n_measured,
         n_unmeasured, reference_prices, disclaimer, method}
    """
    if reference_prices is None:
        reference_prices = dict(DEFAULT_REFERENCE_PRICES)

    axes: List[Dict[str, Any]] = []
    measured_axes: List[Dict[str, Any]] = []

    for axis in sorted(model_scores.keys()):
        score = float(model_scores[axis])
        n = int(n_per_axis.get(axis, 0))
        source = "measured" if n > 0 else "unmeasured"
        axes.append({"axis": axis, "score": score, "n": n, "source": source})
        if source == "measured":
            measured_axes.append({"axis": axis, "score": score, "n": n})

    composite: Optional[float] = None
    composite_method = "no-measured-axes"
    if _HAS_WIRING and measured_axes:
        # precision-weighted mean of MEASURED axes only, via the estate wiring.
        total_w = 0.0
        weighted = 0.0
        for a in measured_axes:
            cs = _ar.from_accuracy(a["axis"], a["score"], a["n"], scale=3.0)
            w = max(cs.precision, 0.0)
            # safety: a zero-precision measured axis (n=0 handled above) can't tilt
            if w > 0.0 or len(measured_axes) == 1:
                weighted += a["score"] * w
                total_w += w
        if total_w > 0.0:
            composite = round(weighted / total_w, 6)
            composite_method = "precision-weighted-mean-of-measured-axes"
    elif measured_axes:
        # documented fallback if the wiring isn't importable: equal-weight mean.
        composite = round(
            sum(a["score"] for a in measured_axes) / len(measured_axes), 6
        )
        composite_method = "equal-weight-mean-of-measured-axes (wiring unavailable)"

    return {
        "entity": entity,
        "assessed_at": assessed_at or _today(),
        "axes": axes,
        "composite": composite,
        "composite_method": composite_method,
        "n_axes": len(axes),
        "n_measured": len(measured_axes),
        "n_unmeasured": len(axes) - len(measured_axes),
        "reference_prices": reference_prices,
        "disclaimer": DISCLAIMER,
        "method": (
            "deterministic exact-grade measurement; composite over MEASURED axes "
            "only; unmeasured never counted as 0"
        ),
    }


def sign_pack(
    pack: Dict[str, Any],
    key_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Wrap the underwriting input in a signed csoai-cose-sign1 Ed25519 envelope.

    Returns {signed, envelope, content_id, time_anchor_state} plus an 'error'
    key when signing is impossible (honest — never faked).
    """
    if not _HAS_WIRING:
        return {
            "signed": False,
            "envelope": None,
            "content_id": None,
            "time_anchor_state": "unsigned",
            "error": "cose_wrapper not importable — cannot sign",
        }
    key_path = key_path or DEFAULT_KEY_PATH
    res = _cose_wrap(pack, source="underwriting-input", key_path=key_path)
    return {
        "signed": res.signed,
        "envelope": res.envelope if res.signed else None,
        "content_id": res.content_id,
        "time_anchor_state": res.time_anchor_state,
        "error": res.error,
    }


def self_test() -> int:
    """Prove honesty + determinism + signing. Prints PASS/FAIL, 0 on success."""
    ok = fail = 0

    def t(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f"  PASS  {name}")
        else:
            fail += 1
            print(f"  FAIL  {name} {extra}")

    fixed_when = "2026-08-14T00:00:00+00:00"

    # --- REAL board data from boards-v2-2026-08-12 (best-model accuracy per axis) ---
    # board_care: best sov6-ethics-v3-light, n=200, acc=0.535
    # board_det:  best sov6-destruction-v3-light, n=33, acc=0.8485
    # board_gov:  best sov6-preservation-v3-light, n=237, acc=0.6667
    # board_art5: best sov6-agency-v3-light, n=36, acc=0.9444  (tie w/ preservation)
    real = {"care": 0.535, "det": 0.8485, "gov": 0.6667, "art5": 0.9444}
    real_n = {"care": 200, "det": 33, "gov": 237, "art5": 36}

    # (a) composite includes ONLY measured axes; unmeasured excluded, never 0
    measured_plus_unmeasured = dict(real)
    measured_plus_unmeasured["xtreme"] = 0.05  # n=0 -> unmeasured
    p = build_underwriting_input(
        "board-real-demo", measured_plus_unmeasured, dict(real_n),
        assessed_at=fixed_when,
    )
    unmeasured = [a for a in p["axes"] if a["source"] == "unmeasured"]
    t("unmeasured axis flagged", any(a["axis"] == "xtreme" for a in unmeasured))
    t("unmeasured axis excluded from axes count mismatch",
      p["n_measured"] == 4 and p["n_unmeasured"] == 1, f"{p['n_measured']}/{p['n_unmeasured']}")
    # Composite must NOT equal an equal-weight mean of all 5 (which would include
    # the 0.05 unmeasured as 0-ish). Composite over the 4 measured only.
    eq_all = sum(list(real.values()) + [0.05]) / 5.0
    t("composite over measured only", p["composite"] is not None and
      abs(p["composite"] - eq_all) > 0.01,
      f"composite={p['composite']} vs eq-all={eq_all:.4f}")

    # (b) deterministic for same inputs — byte-identical axes + composite
    d = real  # all measured
    n = real_n
    p1 = build_underwriting_input("det", d, n, assessed_at=fixed_when)
    p2 = build_underwriting_input("det", d, n, assessed_at=fixed_when)
    pre_axes = str(p1["axes"]) == str(p2["axes"])
    pre_comp = p1["composite"] == p2["composite"]
    t("deterministic axes", pre_axes)
    t("deterministic composite", pre_comp)

    # unmeasured axis does NOT silently count as 0 — composite excludes it entirely
    p_mixed = build_underwriting_input(
        "mix", measured_plus_unmeasured, dict(real_n), assessed_at=fixed_when)
    # manually recompute: precision-weighted over the 4 measured only
    expected = build_underwriting_input("det", real, real_n, assessed_at=fixed_when)["composite"]
    t("unmeasured not counted as 0 (equals measured-only composite)",
      p_mixed["composite"] == expected, f"{p_mixed['composite']} vs {expected}")

    # (c) sign_pack produces signed=True and envelope verifies
    s = sign_pack(p1)
    t("sign_pack signed=True", s.get("signed") is True, str(s.get("error")))
    t("content_id present", bool(s.get("content_id")) and len(s.get("content_id") or "") == 64)
    if s.get("signed") and s.get("envelope"):
        import json as _json
        env = _json.loads(s["envelope"])
        vv = _cose_verify(env)
        t("envelope verifies via cose_wrapper.verify", vv.get("valid") is True, str(vv))
        # envelope source == underwriting-input
        t("envelope source is underwriting-input",
          env.get("payload", {}).get("source") == "underwriting-input")
    else:
        t("envelope verifies via cose_wrapper.verify", False, "not signed")
        t("envelope source is underwriting-input", False)

    # (d) disclaimer present in pack
    t("disclaimer present", "disclaimer" in p1 and DISCLAIMER in p1["disclaimer"])
    t("disclaimer exact wording present in composite record too",
      ("NOT a policy, quote, certification, or legal advice") in p1["disclaimer"])

    # honest contract: reference prices reference real underwriters
    rp = p1.get("reference_prices", {})
    t("munich_re reference present", "munich_re_aisure" in rp)
    t("armilla reference present", "armilla" in rp)
    t("aiuc1 reference present", "aiuc1" in rp)

    print(f"selftest {ok}/{ok + fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
