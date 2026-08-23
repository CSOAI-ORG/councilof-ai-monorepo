#!/usr/bin/env python3
"""eat_chain — wire the EAT evidence chain over a set of signed axis cards.

EAT 7-box: measured -> CI'd -> signed -> CHAINED -> ANCHORED -> BOARDED -> MIRRORED.
This script consumes the Ed25519-signed card-*.signed.json produced by
run_eunomia_axis.py + sign_result.py, hash-chains them (each card links the prior
content_id), computes a chain root, signs the root as a chain anchor (EAT box 5),
writes a human/agent readable EAT board (box 6), and emits a mirror bundle (box 7)
that a backup job (Oracle / RunPod volume) can copy.

Usage:
  python3 eat_chain.py [--dir .] [--glob "card-*.signed.json"] [--key sigil_ed25519.key]
                       [--board eat-board.json] [--mirror eat-mirror/]
"""
from __future__ import annotations

import argparse, glob, hashlib, json, os, time
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

AXIS_ORDER = ["bond-router", "insurance", "stock-market", "east-west",
              "sme-fractional", "agent-economy", "data-dao", "eunomia-token"]


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(v):
    if isinstance(v, dict):
        return "{" + ",".join(canonical(k) + ":" + canonical(v[k]) for k in sorted(v)) + "}"
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, str):
        return json.dumps(v)
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--glob", default="card-*.signed.json")
    ap.add_argument("--key", default="sigil_ed25519.key")
    ap.add_argument("--board", default="eat-board.json")
    ap.add_argument("--mirror", default="eat-mirror")
    args = ap.parse_args()

    d = Path(args.dir)
    cards = sorted(Path(p) for p in glob.glob(str(d / args.glob)))
    if not cards:
        print("no signed cards found", file=os.sys.stderr)
        return 2

    # Order deterministically by the AXIS_ORDER ranking (unknown axes appended, sorted).
    def rank(p: Path) -> int:
        name = p.name
        for i, ax in enumerate(AXIS_ORDER):
            if ax in name:
                return i
        return len(AXIS_ORDER)

    cards.sort(key=rank)

    prev_id = None
    chain = []
    ids = []
    for p in cards:
        card = json.loads(p.read_text())
        cid = card.get("content_id")
        if not cid:
            continue
        ids.append(cid)
        chain.append({"axis": card.get("axis", p.stem), "content_id": cid,
                      "accuracy": card.get("accuracy"), "ci": [card.get("ci95_low"), card.get("ci95_high")],
                      "n": card.get("n_items"), "prev": prev_id})
        prev_id = cid

    if not chain:
        print("no chainable cards", file=os.sys.stderr)
        return 2

    # EAT box 4: chain root.
    root = sha256("|".join(ids).encode())
    # EAT box 5: anchor = Ed25519 signature over the chain root.
    key = Ed25519PrivateKey.from_private_bytes(Path(args.key).read_bytes()[:32])
    anchor_sig = key.sign(root.encode()).hex()
    anchor = {
        "schema": "csoai.eat-chain/0.1",
        "root": root,
        "n": len(chain),
        "axes": [c["axis"] for c in chain],
        "anchor_sig": "ed25519:" + anchor_sig,
        "anchored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "signer": "did:web:csoai.org#estate-chain-1",
    }

    # EAT box 6: board (index).
    board = {"chain": chain, "anchor": anchor}
    Path(args.board).write_text(json.dumps(board, indent=2))
    print(f"chain root: {root}")
    print(f"anchor_sig: {anchor_sig[:32]}…")
    print(f"board: {args.board} ({len(chain)} cards chained)")

    # EAT box 7: mirror bundle — copy cards + board + a manifest into the mirror dir.
    mir = Path(args.mirror)
    mir.mkdir(parents=True, exist_ok=True)
    for p in cards:
        (mir / p.name).write_text(p.read_text())
    (mir / Path(args.board).name).write_text(Path(args.board).read_text())
    manifest = {"root": root, "n": len(chain), "mirrored_at": anchor["anchored_at"],
                "files": [p.name for p in cards] + [Path(args.board).name]}
    (mir / "MIRROR_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"mirror: {mir} ({len(cards)+1} artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
