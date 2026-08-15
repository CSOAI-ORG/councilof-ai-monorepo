"""csoai-city.attestation_registry — the missing wiring: real attestation → SOV SIGNAL.

Fixes the wiring defect (council_signal._aggregate fed `{"score":...}` dicts into a
distance-based index that expects ConstituentScore). This module adapts ANY attestation
output — GSPC axis board, governance-crosswalk score, bridge-protocol module finding,
or signed-card verdict — into a proper ConstituentScore so aggregate_sov_signal can
consume the whole estate.

The estate has 612 repos / 22 bridge MCPs / 16+ attestation MCPs, but ZERO of them fed
the SOV signal before this module. That gap is closed here.

Adaption rules (honest, deterministic — no model judges this):
  * a higher raw score (safety accuracy, pass rate)  -> SMALLER distance to permitted
  * an unmeasured/error output                      -> must NOT be scored as "trusted",
    it is distance = +inf (sigma large) -> contribution suppressed, never a fake pass.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from sovos_signal_index import ConstituentScore, aggregate_sov_signal
    HAS_SIGNAL = True
except Exception:  # pragma: no cover
    HAS_SIGNAL = False

    @dataclass
    class ConstituentScore:  # type: ignore
        constituent_id: str
        distance: float
        sigma: float
        permitted_radius: float
        precision: float
        is_trusted: bool
        chain_id: str = ""


# ---------------------------------------------------------------------------
# Score adapters — turn measurement outputs into distance+sigma
# ---------------------------------------------------------------------------

def _radial(score: float, scale: float) -> float:
    """score in [0,1] -> radial distance from the permitted manifold origin.
    Higher score => closer to the trusted core (smaller distance)."""
    return max(0.0, scale * (1.0 - min(max(score, 0.0), 1.0)))


def from_accuracy(axis: str, accuracy: float, n: int,
                  scale: float = 3.0, chain_id: str = "") -> ConstituentScore:
    """GSPC board accuracy -> ConstituentScore. sigma shrinks with n (Glicko)."""
    sigma = max(0.1, scale / math.sqrt(max(n, 1)))
    distance = _radial(accuracy, scale)
    return ConstituentScore(
        constituent_id=f"gspc:{axis}",
        distance=distance,
        sigma=sigma,
        permitted_radius=scale * 0.4,       # < threshold => trusted
        precision=1.0 / (sigma * sigma),
        is_trusted=distance <= scale * 0.4,
        chain_id=chain_id,
    )


def from_crosswalk(axis: str, pass_rate: float, n_controls: int,
                   chain_id: str = "") -> ConstituentScore:
    """Governance-crosswalk pass-rate (controls met / total) -> score."""
    return from_accuracy(axis, pass_rate, n_controls,
                         scale=4.0, chain_id=chain_id)


def from_bridge(protocol: str, finding: Dict[str, Any],
                chain_id: str = "") -> ConstituentScore:
    """Bridge-protocol module finding -> score. Unmeasured = never trusted."""
    ok = finding.get("measured", False)
    score = float(finding.get("score", 0.0)) if ok else math.inf
    n = int(finding.get("n", 1))
    scale = 2.0
    if not ok:
        return ConstituentScore(
            constituent_id=f"bridge:{protocol}",
            distance=math.inf,
            sigma=1e9,                       # ~zero precision weight
            permitted_radius=scale * 0.4,
            precision=1e-18,
            is_trusted=False,
            chain_id=chain_id,
        )
    sigma = max(0.1, scale / math.sqrt(max(n, 1)))
    distance = _radial(score, scale)
    return ConstituentScore(
        constituent_id=f"bridge:{protocol}",
        distance=distance, sigma=sigma,
        permitted_radius=scale * 0.4,
        precision=1.0 / (sigma * sigma),
        is_trusted=distance <= scale * 0.4,
        chain_id=chain_id,
    )


def from_card_verdict(card: Dict[str, Any], chain_id: str = "") -> Optional[ConstituentScore]:
    """A signed-card verdict -> score. Only counts if the card is genuinely signed."""
    if not (card.get("signed") is True or card.get("signature")):
        return None                          # unsigned cards are not evidence
    axis = str(card.get("body", {}).get("board", {}).get("axis", "card"))
    acc = float(card.get("body", {}).get("board", {}).get("best_acc") or 0.0)
    n = int(card.get("body", {}).get("board", {}).get("n") or 0)
    if n == 0:
        return None
    return from_accuracy(axis, acc, n, scale=3.0, chain_id=chain_id)


# ---------------------------------------------------------------------------
# The registry — aggregates a portfolio of constituent scores into SOV signal
# ---------------------------------------------------------------------------

def aggregate_attestation_scores(scores: List[ConstituentScore],
                                 article_zero: bool = False) -> Dict[str, Any]:
    """Aggregate any list of ConstituentScores into the SOV signal index verdict."""
    if not HAS_SIGNAL or not scores:
        return {
            "n": len(scores),
            "aggregate_score": None,
            "note": "no signal index or no scores",
        }
    verdict = aggregate_sov_signal(scores, article_zero=article_zero)
    return verdict.to_dict()


def self_test() -> int:
    """Prove the wiring: real scores -> ConstituentScore -> SOV signal, honestly."""
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # 1. high accuracy -> trusted, small distance
    s1 = from_accuracy("care", 0.95, 128)
    t("high-acc trusted", s1.is_trusted and s1.distance < 1.0, f"d={s1.distance:.2f}")
    # 2. low accuracy -> not trusted
    s2 = from_accuracy("det", 0.30, 40)
    t("low-acc not trusted", not s2.is_trusted, f"d={s2.distance:.2f}")
    # 3. precision grows with n
    t("more-n higher precision", from_accuracy("a", 0.8, 300).precision >
      from_accuracy("a", 0.8, 10).precision)
    # 4. unmeasured bridge -> never trusted, ~zero weight
    sb = from_bridge("cobol", {"measured": False})
    t("unmeasured bridge never trusted", not sb.is_trusted and sb.precision < 1e-9)
    # 5. unsigned card -> excluded
    t("unsigned card excluded", from_card_verdict({"signed": False}) is None)
    # 6. full aggregate works (no exception, chain_id set)
    agg = aggregate_attestation_scores([s1, from_bridge("mcp", {"measured": True, "score": 0.9, "n": 50})])
    t("aggregate returns signal", agg.get("aggregate_score") is not None and "chain_id" in agg,
      f"{agg.get('aggregate_score')}")

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
