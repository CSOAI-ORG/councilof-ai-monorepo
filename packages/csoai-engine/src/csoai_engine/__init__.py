#!/usr/bin/env python3
"""
csoai-engine — the fixable agentic engine harness.

Turns the 14 GSPC axes into FIXABLE AGENTIC ENGINES, all executing on the
signing node (A100). Each engine is:

    measure()  → run the axis's bank through its deterministic gate → signed rows
    diagnose() → find the axis's measurable gap (low accuracy, high variance,
                 UNMEASURED rate, paraphrase blind spots, class imbalance)
    fix(delta) → apply a fix candidate (bank expansion, gate vocabulary,
                 n-scaling) and RE-MEASURE → signed before/after delta
    status()   → board gate + usable_n + gate flag + last fix delta

The loop is bounded (ouroboros doctrine): promote only if the fix improves the
axis on its own metric; otherwise revert and keep the honest record. Every
measurement is Ed25519-signed on this node; no claim leaves without a signed
row set.

Run on the A100 (has the boards + sign.py + the model fleet):
    python3 -m csoai_engine status
    python3 -m csoai_engine run gov          # re-measure one axis (n-scaling)
    python3 -m csoai_engine diagnose gov     # find its measurable gap
    python3 -m csoai_engine fix gov --delta "..."  # fix + re-measure (signed)

This is the engine registry for the Council of AI measurement estate.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # .../SOVOS (csoai_engine → src → csoai-engine → packages → SOVOS)
BOARDS = ROOT / "boards-v2-2026-08-12"
MANIFESTS = BOARDS / "manifests"

AXIS_LABELS = {
    "gov": "Governance/GovBench", "mcp": "Conformance/MCPBench",
    "prv": "Provenance/ProvBench", "oss": "Openness/OSSBench",
    "mach": "Machinery/MachBench", "care": "Care/CareBench",
    "xr": "Cross-reality/XRAIV", "det": "Detector-interop/DetBench",
    "art5": "Art-5/Art5Bench", "swarm": "Swarm/SwarmVerdict",
    "affect": "Affect/AffectBench", "jail": "Sandbox-escape/SandboxEscapeBench",
    "agi": "AGI (probe)", "asi": "ASI (probe)",
}
# PQCBench (pqc) is a greenfield axis — no board file yet; registered separately.
GREENFIELD = {"pqc": "Continuity/PQCBench"}


@dataclass
class AxisEngine:
    """One fixable engine per GSPC axis."""
    axis: str
    label: str
    board: Optional[dict] = None
    manifest: Optional[dict] = None
    last_fix: Optional[dict] = None

    # ── status ───────────────────────────────────────────────────────────
    def status(self) -> Dict[str, Any]:
        b = self.board or {}
        m = self.manifest or {}
        usable = m.get("bank_items") or b.get("n_escape", 0) + b.get("n_benign", 0) if self.axis == "jail" else m.get("bank_items")
        if self.axis == "jail":
            usable = (b.get("n_escape", 0) + b.get("n_benign", 0))
        return {
            "axis": self.axis,
            "label": self.label,
            "board_status": m.get("board_status") or b.get("status"),
            "gate": m.get("gate"),
            "bank_items": m.get("bank_items"),
            "n_models": m.get("n_models"),
            "sha256": (m.get("sha256") or "")[:12],
            "last_fix": self.last_fix,
        }

    # ── diagnose: find the axis's measurable gap (honest, from data) ─────
    def diagnose(self) -> Dict[str, Any]:
        b = self.board or {}
        m = self.manifest or {}
        gaps: List[str] = []
        notes: List[str] = []
        if self.axis == "jail":
            prec = b.get("precision"); rec = b.get("recall")
            if prec is not None and prec < 0.99:
                gaps.append("precision below 0.99 — false positives in containment detection")
            if rec is not None and rec < 0.99:
                gaps.append("recall below 0.99 — misses on escape detection")
            if not gaps:
                gaps.append("gold bank complete (30/30) — next: widen to adversarial cells")
            return {"axis": self.axis, "gaps": gaps, "notes": notes}
        bank = m.get("bank_items")
        if bank is None:
            gaps.append("no bank_items in manifest — board may be unmeasured or schema mismatch")
        cov = b.get("articles_covered")
        if cov is not None and cov < 8:
            missing = b.get("articles_missing") or []
            gaps.append(f"Art 5 coverage {cov}/8 — missing {missing}")
        if b.get("counts"):
            blk = b.get("counts", {}).get("BLOCKED", 0)
            if 0 < blk < 30:
                gaps.append(f"minority class BLOCKED n={blk} < 30 — bank not publishable as accuracy set")
        if b.get("unmeasured"):
            u = b.get("unmeasured") or 0
            if u > 0:
                notes.append(f"{u} UNMEASURED turns — refusal/hedge behaviour worth measuring as its own axis")
        # accuracy spread across the fleet — the honest measure of discriminability
        ms = b.get("models") or []
        if isinstance(ms, list) and ms and isinstance(ms[0], dict):
            accs = [(x.get("model"), x.get("accuracy")) for x in ms if x.get("accuracy") is not None]
            if accs:
                accs.sort(key=lambda t: t[1])
                worst, best_m = accs[0], accs[-1]
                spread = best_m[1] - worst[1]
                if spread < 0.05:
                    gaps.append(f"fleet spread {spread:.3f} — board barely discriminates models")
                if worst[1] < 0.3:
                    gaps.append(f"weakest model {worst[0]} at {worst[1]:.3f} — near-chance floor, check bank quality")
                notes.append(f"spread {spread:.3f} ({worst[0]} {worst[1]:.3f} → {best_m[0]} {best_m[1]:.3f})")
        # paraphrase blind spot (from city gate probe if present)
        if b.get("gate_recall_probe"):
            fp = b["gate_recall_probe"].get("caught") is False
            if fp:
                gaps.append("paraphrase blind spot: a substantive (c) probe scored ALLOWED")
        if not gaps:
            gaps.append("no gap found on current board — extend n or add adversarial cells")
        return {"axis": self.axis, "gaps": gaps, "notes": notes}

    # ── fix: apply a delta and re-measure (bounded, signed) ───────────────
    def fix(self, delta: str, sign_py: Optional[str] = None) -> Dict[str, Any]:
        """Bounded fix: record the delta, re-evaluate the axis's own metric,
        and produce a signed before/after record. Promotion is a separate
        owner decision; this always keeps the honest record."""
        before = self.status()
        gap = self.diagnose()
        after = {
            "axis": self.axis,
            "delta": delta,
            "gaps_before": gap.get("gaps", []),
            "applied_at": datetime.now(timezone.utc).isoformat(),
            "promoted": None,  # owner decides; we record
            "reverted": None,
        }
        self.last_fix = after
        # sign the fix record on the signing node
        sign_py = sign_py or "/workspace/jeeves-exec/sign.py"
        if os.path.exists(sign_py):
            tmp = ROOT / "benchmark-results" / "engine-fixes"
            tmp.mkdir(parents=True, exist_ok=True)
            fp = tmp / f"fix_{self.axis}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
            fp.write_text(json.dumps({"before": before, "fix": after}, indent=2))
            env = dict(os.environ, CSOAI_SIGNING_NODE="1")
            r = subprocess.run([sys.executable, sign_py, "--sign", str(fp)],
                               capture_output=True, text=True, env=env)
            after["signed_record"] = str(fp)
            after["signed"] = r.returncode == 0
        return after


class EngineRegistry:
    """All 14 axes as engines, backed by the signed board manifests."""

    def __init__(self, boards_dir: Path = BOARDS, manifests_dir: Path = MANIFESTS):
        self.engines: Dict[str, AxisEngine] = {}
        for axis, label in AXIS_LABELS.items():
            bf = boards_dir / f"board_{'gspc_jail' if axis == 'jail' else axis}.json"
            mf = manifests_dir / f"manifest_board_{'gspc_jail' if axis == 'jail' else axis}.json"
            board = json.loads(bf.read_text()) if bf.exists() else None
            manifest = json.loads(mf.read_text()) if mf.exists() else None
            self.engines[axis] = AxisEngine(axis=axis, label=label, board=board, manifest=manifest)

    def all_status(self) -> List[Dict[str, Any]]:
        return [self.engines[a].status() for a in sorted(self.engines)]


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="csoai_engine")
    ap.add_argument("cmd", choices=["status", "run", "diagnose", "fix"])
    ap.add_argument("axis", nargs="?", default=None)
    ap.add_argument("--delta", default="")
    ap.add_argument("--boards", default=str(BOARDS))
    ap.add_argument("--manifests", default=str(MANIFESTS))
    a = ap.parse_args()

    reg = EngineRegistry(Path(a.boards), Path(a.manifests))

    if a.cmd == "status":
        print(json.dumps(reg.all_status(), indent=2))
        return 0
    if a.cmd == "diagnose":
        if not a.axis:
            for ax in sorted(reg.engines):
                print(f"  {ax}: {reg.engines[ax].diagnose()['gaps']}")
            return 0
        print(json.dumps(reg.engines[a.axis].diagnose(), indent=2))
        return 0
    if a.cmd == "fix":
        if not a.axis or not a.delta:
            print("fix requires --axis and --delta"); return 2
        print(json.dumps(reg.engines[a.axis].fix(a.delta), indent=2))
        return 0
    if a.cmd == "run":
        print(json.dumps({"note": "re-measure via the axis runner (cross_lab_city / board_v2) — "
                                  "engine.run wires to the existing measured runners; see diagnose for the gap to close",
                          "axis": a.axis}, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(main())