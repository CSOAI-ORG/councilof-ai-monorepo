#!/usr/bin/env python3
"""run_eunomia_axis — measure ONE EUNOMIA financial axis against ONE model.

Reads the frozen item set for `axis` (per generate_eunomia_items.py), grades
exact-label via the generalised gspc score_axis, and emits a JSON result card
that sign_result.py can sign into an Ed25519 card (EAT box 3).

Usage:
  python3 run_eunomia_axis.py <axis> <model> [--out result.json] [--base http://127.0.0.1:11434]
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

from gspc_six_axis_e2e import load_axis, score_axis, AXES


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("axis", choices=sorted(AXES))
    ap.add_argument("model")
    ap.add_argument("--out", default=None)
    ap.add_argument("--base", default="http://127.0.0.1:11434")
    args = ap.parse_args()

    items, field, labels = load_axis(args.axis)
    if not items:
        print(f"No items for axis {args.axis}; run generate_eunomia_items.py first.", file=sys.stderr)
        return 2

    # gspc_six_axis_e2e reads the Ollama endpoint from GOVBENCH_OLLAMA_URL (default localhost).
    import os
    os.environ["GOVBENCH_OLLAMA_URL"] = args.base

    res = score_axis(args.model, items, field, labels)
    res["axis"] = args.axis
    res["bench"] = AXES[args.axis][0]
    res["field"] = field
    res["labels"] = labels

    out = Path(args.out or f"eunomia-{args.axis}-result.json")
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
