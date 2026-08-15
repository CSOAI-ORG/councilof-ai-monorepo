"""CLI:  python -m csoai_city --citizens 50 --epochs 3 --out runs/v0"""
from __future__ import annotations
import argparse, json, random, sys
from pathlib import Path
from .arena import CityRun, build_citizens, ollama_models

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="csoai-city", description="SOV City — governed multi-agent arena")
    ap.add_argument("--citizens", type=int, default=50)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--out", default="runs/v0")
    ap.add_argument("--host", default="http://127.0.0.1:11434")
    ap.add_argument("--models", default="", help="comma-separated; default = every model ollama serves")
    ap.add_argument("--stratified", action="store_true",
                    help="assign each RED citizen one Article 5 subparagraph to probe — "
                         "builds a bank that can discriminate, but the breach rate is then "
                         "NOT a natural incidence rate")
    ap.add_argument("--selftest", action="store_true", help="gate self-test, no models needed")
    a = ap.parse_args(argv)

    if a.selftest:
        from .selftest import run as st
        r = st(); print(json.dumps(r, indent=2)); return 0 if r["ok"] else 1

    models = [m.strip() for m in a.models.split(",") if m.strip()] or ollama_models(a.host)
    if not models:
        print(f"NO MODELS: {a.host}/api/tags returned nothing. Refusing to run an empty city "
              f"rather than emit a board with no citizens.", file=sys.stderr)
        return 2
    cits = build_citizens(models, a.citizens, random.Random(7), stratified=a.stratified)
    print(f"SOV CITY · {len(cits)} citizens · {len(models)} models · {a.epochs} epochs · "
          f"design={'stratified' if a.stratified else 'natural'} -> {a.out}", flush=True)
    board = CityRun(Path(a.out), cits, epochs=a.epochs, host=a.host).run()
    print(json.dumps(board, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
