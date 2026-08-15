#!/usr/bin/env python3
"""fleet_power.py — how many models must a fleet hold before "dead item" means anything?

THE ERROR THIS EXISTS TO PREVENT, WHICH I MADE
----------------------------------------------
On 2026-08-04 I measured 90 GSPC items across 8 models, found 35 "dead" (every model passes or
none does), and wrote in DISCRIMINATING_ITEMS_SPEC: *"What is robust is the dead-item count,
which needs no correlation at all."*

That was exactly backwards. The dead-item count is the MOST fleet-sensitive statistic in the
set, because an item is called dead on unanimity, and unanimity is cheap when N is small.

Re-running the identical 90 items across 30 models: governance dead 5 -> 1, safety dead 12 -> 1.
Most of those items were never dead. They were under-sampled.

THE ARITHMETIC
--------------
An item with a true per-model pass-probability p looks dead when all N models happen to land on
the same side:

    P(looks dead) = p^N + (1-p)^N

At N=8 and p=0.8 that is 0.168 — roughly one in six genuinely-usable items will be misclassified
as dead. At N=30 it is 0.0012. The statistic does not stabilise gradually; it collapses.

This module answers the design question directly: given a tolerable false-dead rate, how many
models does the fleet need? And it refuses to certify a dead-item count taken below that.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def p_looks_dead(p: float, n: int) -> float:
    return p ** n + (1 - p) ** n


def min_fleet(p_hardest: float = 0.85, tolerance: float = 0.05, cap: int = 200) -> int:
    """Smallest N where even the most lopsided item we care about stays under `tolerance`.

    p_hardest is the most extreme TRUE pass-rate still considered a live item. Items genuinely
    at p=0.99 will look dead at any feasible N, and that is correct — they are nearly dead.
    """
    for n in range(3, cap + 1):
        if p_looks_dead(p_hardest, n) <= tolerance:
            return n
    return cap


def certify(n_models: int, p_hardest: float = 0.85, tolerance: float = 0.05) -> tuple[bool, str]:
    need = min_fleet(p_hardest, tolerance)
    if n_models >= need:
        return True, (f"fleet of {n_models} >= {need} required; false-dead rate at p={p_hardest} "
                      f"is {p_looks_dead(p_hardest, n_models):.4f}")
    return False, (f"REFUSED: fleet of {n_models} is below the {need} needed for a trustworthy "
                   f"dead-item count. At p={p_hardest} the false-dead rate is "
                   f"{p_looks_dead(p_hardest, n_models):.3f} — roughly "
                   f"{p_looks_dead(p_hardest, n_models) * 100:.0f}% of live items would be "
                   f"misread as dead.")


def selftest() -> bool:
    ok = True
    checks = [
        ("monotone in N", all(p_looks_dead(0.8, n) >= p_looks_dead(0.8, n + 1)
                              for n in range(3, 40))),
        ("symmetric in p", abs(p_looks_dead(0.3, 10) - p_looks_dead(0.7, 10)) < 1e-12),
        ("p=0.5 is the safest case", all(p_looks_dead(0.5, 12) <= p_looks_dead(p, 12)
                                         for p in (0.6, 0.7, 0.8, 0.9))),
        ("N=8 fails certification", not certify(8)[0]),
        ("N=30 passes certification", certify(30)[0]),
        ("min_fleet is at least 3", min_fleet() >= 3),
    ]
    for name, good in checks:
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] {name}")
    print(f"  selftest {'GREEN' if ok else 'RED'}")
    return bool(ok)


def main():
    if not selftest():
        sys.exit("selftest failed")
    print("\nP(a live item LOOKS dead) = p^N + (1-p)^N\n")
    ns = (8, 13, 20, 30, 50, 80)
    print(f"  {'p':>5s} " + " ".join(f"N={n:<8d}" for n in ns))
    for p in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95):
        print(f"  {p:>5.2f} " + " ".join(f"{p_looks_dead(p, n):<10.4f}" for n in ns))

    print("\n  minimum fleet size for a trustworthy dead-item count:")
    for p_h, tol in ((0.85, 0.05), (0.90, 0.05), (0.85, 0.01), (0.90, 0.01)):
        print(f"    tolerate {tol:.0%} false-dead at p={p_h}:  N >= {min_fleet(p_h, tol)}")

    print("\n  certification of the runs actually performed:")
    for n, label in ((8, "axis-saturation first run"), (13, "care_battery item-quality"),
                     (30, "axis-saturation scaled run")):
        ok, why = certify(n)
        print(f"    N={n:<3d} {label:32s} {'CERTIFIED' if ok else 'NOT CERTIFIED'}")
        print(f"          {why}")

    out = HERE / "evidence/harness/freeze/latest/fleet-power.json"
    out.write_text(json.dumps({
        "built_at": datetime.now(timezone.utc).isoformat(),
        "purpose": ("establishes the minimum model-fleet size at which a dead-item count is "
                    "trustworthy, after a measured failure: 90 items at N=8 gave 35 dead; the "
                    "same 90 items at N=30 gave governance 1 and safety 1."),
        "formula": "P(looks dead) = p^N + (1-p)^N",
        "corrects": ("DISCRIMINATING_ITEMS_SPEC claimed the dead-item count was the robust "
                     "statistic requiring no correlation. It is the MOST fleet-sensitive "
                     "statistic, because deadness is decided by unanimity and unanimity is "
                     "cheap at small N."),
        "min_fleet_5pct_at_p085": min_fleet(0.85, 0.05),
        "min_fleet_1pct_at_p090": min_fleet(0.90, 0.01),
        "table": {str(n): {str(p): round(p_looks_dead(p, n), 6)
                           for p in (0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95)} for n in ns},
        "certifications": {str(n): certify(n)[0] for n in (8, 13, 30)}}, indent=2))
    print(f"\n  -> {out}")


if __name__ == "__main__":
    main()
