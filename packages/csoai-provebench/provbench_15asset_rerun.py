#!/usr/bin/env python3
"""provbench_15asset_rerun.py — Re-run provenance benchmark with 15 assets including new COSE ML-DSA-65 binding.

After adding the cose_ml_dsa_65 binding type to survival_matrix.py, this script re-runs
the matrix with 15 assets and produces a fresh canonical-bound JSON.

Usage:
    python3 provbench_15asset_rerun.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))

from survival_matrix import run_matrix, survival_ci, TRANSFORMS, selftest


def build_cells(n_assets: int = 15) -> list:
    """Build 15 test cells with mix of binding types including new COSE ML-DSA-65."""
    bindings = [
        ("hard_hash", 5),
        ("metadata_xmp", 4),
        ("soft_watermark", 3),
        ("cose_ml_dsa_65", 3),  # New PQC binding
    ]
    cells = []
    counter = 0
    for binding, count in bindings:
        for i in range(count):
            counter += 1
            cells.append({
                "asset_id": f"asset_{counter:03d}",
                "binding": binding,
            })
    return cells[:n_assets]


def main():
    # Selftest first
    ok, msg = selftest()
    if not ok:
        print(f"FAIL: {msg}")
        return 1
    print(f"OK: {msg}")

    cells = build_cells(15)
    print(f"\nRunning matrix on {len(cells)} assets across {len(TRANSFORMS)} transforms...")

    # Print binding distribution
    from collections import Counter
    binding_dist = Counter(c["binding"] for c in cells)
    for binding, count in binding_dist.items():
        print(f"  {binding}: {count} assets")

    # Run the matrix
    result = run_matrix(cells)

    # Calculate survival CI
    ci = survival_ci(result["n_survive"], result["n_total"])

    # Build canonical-bound JSON
    canonical = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_assets": len(cells),
        "n_cells": len(cells) * (len(TRANSFORMS) - 1),  # minus identity
        "binding_distribution": dict(binding_dist),
        "transforms": TRANSFORMS,
        "results": {
            "n_survive": result["n_survive"],
            "n_total": result["n_total"],
            "ci": ci,
        },
        "cells": cells,
        "matrix_rows": result["rows"][:10],  # First 10 rows for evidence
    }

    # Write output
    output_path = Path("benchmark-results/provbench-15asset-2026-07-30.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(canonical, indent=2))

    # Report
    print(f"\n=== RESULTS ===")
    print(f"  Assets: {len(cells)}")
    print(f"  Cells (transforms × assets, excl identity): {len(cells) * (len(TRANSFORMS) - 1)}")
    print(f"  Survived (binding-intact): {result['n_survive']}/{result['n_total']}")
    print(f"  Rule-of-three upper: {ci.get('rule_of_three_upper_95', 'N/A')}")
    print(f"  Survival rate: {ci.get('survival_rate', 'N/A')}")

    print(f"\n-> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())