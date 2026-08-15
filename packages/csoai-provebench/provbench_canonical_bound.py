"""
provbench_canonical_bound.py — produce THE canonical ProvBench CI before announcement.

After this runs once, both n=12 and n=20 print the SAME bound text on every artifact.
The number we publish is the ASSET-LEVEL, not the trial-level.
It is computed honestly: rule-of-three on observed survival events, with the
clustering caveat baked into the label.

    python3 provbench_canonical_bound.py
    python3 provbench_canonical_bound.py --selftest
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import math


def wilson_lower_bound(p: float, n: int, z: float = 1.6449) -> float:
    """One-sided lower bound on a binomial proportion (z=1.6449 → 95% one-sided)."""
    if n == 0:
        return 0.0
    denom = 1.0 + (z ** 2) / n
    centre = (p + (z ** 2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + (z ** 2) / (4 * n ** 2))
    return max(0.0, centre - margin)


def wilson_upper_bound(p: float, n: int, z: float = 1.6449) -> float:
    if n == 0:
        return 1.0
    denom = 1.0 + (z ** 2) / n
    centre = (p + (z ** 2) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + (z ** 2) / (4 * n ** 2))
    return min(1.0, centre + margin)


def rule_of_three_upper(k: int, n: int) -> float:
    """Rule of three: 0/k events ⇒ true rate is at most 3/n with 95% confidence."""
    if k > 0:
        return None
    return 3.0 / n


def selftest() -> bool:
    ok = True
    # Rule of three at n=12, 0 events: 3/12 = 0.25
    r = rule_of_three_upper(0, 12)
    if abs(r - 0.25) > 1e-9:
        print(f"FAIL  rule_of_three(0,12) = {r}, expected 0.25")
        ok = False
    # Rule of three at n=20, 0 events: 3/20 = 0.15
    r = rule_of_three_upper(0, 20)
    if abs(r - 0.15) > 1e-9:
        print(f"FAIL  rule_of_three(0,20) = {r}, expected 0.15")
        ok = False
    # Wilson at p=0, n=20: just the z^2/(2n) / denom term
    w = wilson_upper_bound(0.0, 20)
    if w <= 0 or w > 0.20:
        print(f"FAIL  wilson_upper(0,20) = {w}, expected in (0, 0.20)")
        ok = False
    # k>0 must return None
    if rule_of_three_upper(1, 20) is not None:
        print("FAIL  rule_of_three with k>0 must return None")
        ok = False
    if ok:
        print("  PASS  rule_of_three(0,12)=0.25")
        print("  PASS  rule_of_three(0,20)=0.15")
        print("  PASS  wilson_upper_bound finite in (0,1)")
        print("  PASS  k>0 returns None for rule_of_three")
        print("selftest 4/4")
    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()

    if args.selftest:
        if not selftest():
            sys.exit(1)
        return

    here = Path(__file__).resolve().parent

    # Per-asset survival: the binding check is what distinguishes a real survivor
    # from a manifest transplant. The two transforms that always destroy it
    # (jpeg_reencode, strip_metadata) were 0/20 on binding_intact.
    # asset n here is 20, trial n is 180 (= 9 transforms × 20 assets for the killing ones).

    n = 20  # independent assets
    k = 0   # observed survivors on binding_intact across the killing transforms

    point = k / n
    upper_rule_of_three = rule_of_three_upper(k, n)
    upper_wilson = wilson_upper_bound(point, n)

    print("=" * 70)
    print("PROVBENCH CANONICAL BOUND — one number for both n=12 and n=20")
    print("=" * 70)
    print()
    print(f"  k = {k} survivors / n = {n} independent assets")
    print(f"  Point estimate: {point:.0%}")
    print()
    print("  CANONICAL TEXT (paste into DR-NEW and every artifact):")
    print()
    print(f"    '0 of {n} assets survived binding-intact across the killing")
    print(f"     transforms (jpeg_reencode, strip_metadata). Rule-of-three upper")
    print(f"     bound 95%: {upper_rule_of_three:.1%}. Cells cluster by (asset,")
    print(f"     binding), so naive pooled CI is not applicable.'")
    print()
    print(f"  Wilson 95% one-sided upper: {upper_wilson:.1%}")
    print(f"  Rule-of-three 95% upper:    {upper_rule_of_three:.1%}")
    print()
    print("  Both bounds exist. The rule-of-three is the conservative one and")
    print("  the only honest one when the asset count is the unit — clustered")
    print("  CIs assume the SAME asset is failing on EVERY transform, which is")
    print("  exactly what we observe (it is the binding mechanism, not the")
    print("  transform, that destroys the manifest).")

    # Reconciliation: DR-0001 had 24.2% / 3.43% / 22.1%.
    # The canonical text above subsumes all three because:
    #   - 24.2% is the n=12 one-sided upper (asset as unit) — superseded by 11.9% from n=20.
    #   - 3.43% is the n=108 cell-level upper (treats cells as independent) — invalid.
    #   - 22.1% is the n=12 two-sided Wilson upper — superseded by 16.1% from n=20.
    print()
    print("  RECONCILIATION WITH PRIOR RECORDS")
    print(f"  DR-0001 (24.2% n=12 one-sided)  → superseded: {upper_wilson:.1%} (n={n} one-sided)")
    print(f"  DR-0001 (3.43% n=108)           → SUPERSEDED: independence assumption invalid")
    print(f"  DR-0001 (22.1% n=12 two-sided)  → superseded: {wilson_upper_bound(point, n, z=1.96):.1%} (n={n} two-sided)")
    print()

    out = {
        "canonical": {
            "text": f"0 of {n} assets survived binding-intact across the killing transforms (jpeg_reencode, strip_metadata). Rule-of-three upper bound 95%: {upper_rule_of_three:.1%}. Cells cluster by (asset, binding), so naive pooled CI is not applicable.",
            "k": k,
            "n_assets": n,
            "rule_of_three_upper": upper_rule_of_three,
            "wilson_one_sided_upper": upper_wilson,
            "wilson_two_sided_upper": wilson_upper_bound(point, n, z=1.96),
        },
        "reconciliation": {
            "DR-0001 n=12 one-sided 24.2%": f"superseded by {upper_wilson:.1%}",
            "DR-0001 n=108 cell 3.43%": "independence assumption invalid",
            "DR-0001 n=12 two-sided 22.1%": f"superseded by {wilson_upper_bound(point, n, z=1.96):.1%}",
        },
    }
    out_path = here / "benchmark-results" / "provbench-canonical-bound.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
