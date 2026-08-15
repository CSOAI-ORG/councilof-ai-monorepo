"""DURABLE_BOARD — run the 13-axis board so no reboot can lose a completed axis.

The lesson paid for in blood this session: an ephemeral pod reboots and wipes
/workspace, /root, and the models. A board run that writes only to local disk
loses every axis that hadn't finished — and this happened: 2 of 12 axes survived
only because they were parked to a persistent volume before the restart.

This runner makes durability the default, not an afterthought:

  * Banks are PULLED FROM HF each run (csoai/gspc-*), so the pod needs no local
    bank state to survive.
  * Each axis's board + per-item rows are PUSHED TO HF the instant that axis
    finishes (csoai/gspc-boards). HF survived every reboot and endpoint drift
    this session; it is the store that actually holds.
  * The run RESUMES from HF: an axis whose board already exists on HF is skipped.
    A reboot costs at most the single in-flight axis, never the finished ones.

Two durable stores, not one: the persistent VOLUME (/runpod, survives reboots)
and HF (survives the pod being deleted). Each finished axis lands on the volume,
then HF — safe on two machines. "Never lose a piece" is true only when the
pieces land somewhere that outlives the pod, and now they land in two such
places, one axis at a time, the moment it is earned.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

# Axis code -> (canonical name, HF bank slug)
AXES: Dict[str, Tuple[str, str]] = {
    "gov": ("governance", "csoai/gspc-gov"),
    "agi": ("safety", "csoai/gspc-agi"),
    "prv": ("provenance", "csoai/gspc-prv"),
    "asi": ("continuity", "csoai/gspc-asi"),
    "mcp": ("conformance", "csoai/gspc-mcp"),
    "oss": ("openness", "csoai/gspc-oss"),
    "mach": ("machinery-conformity", "csoai/gspc-mach"),
    "care": ("care", "csoai/gspc-care"),
    "xr": ("cross-reality", "csoai/gspc-xr"),
    "det": ("detector-interop", "csoai/gspc-det"),
    "art5": ("art5-safeguard", "csoai/gspc-art5"),
    "swarm": ("swarm", "csoai/gspc-swarm"),
    "affect": ("affect", "csoai/gspc-affect"),   # the 13th
}

BOARDS_REPO = "csoai/gspc-boards"   # off-box durable store (survives pod deletion)

# Two durability layers, not one — "two machines or it doesn't count":
#   1. the PERSISTENT VOLUME (/runpod) — on-box, survives reboots. This is the
#      layer that actually saved 2 boards this session when the pod restarted.
#   2. HF (BOARDS_REPO) — off-box, survives the pod being deleted entirely.
# The volume protects against reboot; HF protects against total loss. A finished
# axis is written to the volume first, then pushed to HF — safe on two machines.
VOLUME_ROOTS = ("/runpod", "/workspace/persist", "/mnt/vol")


def default_work() -> Path:
    """Prefer a persistent volume for the work dir; fall back to /tmp with a warning.
    Writing to an ephemeral path is the exact mistake the reboot punished."""
    for root in VOLUME_ROOTS:
        p = Path(root)
        if p.is_dir() and os.access(root, os.W_OK):
            return p / "sovos-boards"
    print("  WARNING: no persistent volume found — writing to /tmp (ephemeral). "
          "A reboot will lose in-flight work; only the HF push is durable here.", flush=True)
    return Path("/tmp/sovos-boards")


def _hf_api():
    from huggingface_hub import HfApi  # imported lazily so the module loads without hub
    tok = os.environ.get("HF_TOKEN")
    if not tok:
        p = Path.home() / ".cache" / "huggingface" / "token"
        tok = p.read_text().strip() if p.exists() else None
    return HfApi(token=tok)


def already_done(api, code: str) -> bool:
    """An axis is done only if its board is already on HF AND MEASURED. An
    UNMEASURED board means a prior (weaker) fleet couldn't score it — a richer
    fleet must be allowed to retry, so we do NOT skip UNMEASURED axes. This keeps
    the resume durable without freezing a weak result in place."""
    try:
        from huggingface_hub import hf_hub_download
        if f"board_{code}.json" not in api.list_repo_files(BOARDS_REPO, repo_type="dataset"):
            return False
        f = hf_hub_download(BOARDS_REPO, f"board_{code}.json", repo_type="dataset")
        return json.loads(Path(f).read_text()).get("status") == "MEASURED"
    except Exception:
        return False


def fetch_bank(slug: str, dest: Path) -> Path:
    from huggingface_hub import hf_hub_download
    f = hf_hub_download(slug, "items.jsonl", repo_type="dataset")
    dest.write_bytes(Path(f).read_bytes())
    return dest


def push_axis(api, code: str, board_path: Path, peritem_path: Optional[Path]) -> None:
    """Upload one finished axis to HF immediately. This is the durability event:
    after this returns, a reboot cannot lose this axis."""
    api.create_repo(BOARDS_REPO, repo_type="dataset", exist_ok=True)
    api.upload_file(path_or_fileobj=str(board_path), path_in_repo=f"board_{code}.json",
                    repo_id=BOARDS_REPO, repo_type="dataset",
                    commit_message=f"durable board: {code} landed")
    if peritem_path and peritem_path.exists():
        api.upload_file(path_or_fileobj=str(peritem_path), path_in_repo=f"peritem_{code}.jsonl",
                        repo_id=BOARDS_REPO, repo_type="dataset",
                        commit_message=f"durable board: {code} per-item rows")


def run(models: List[str], ask_fn: Callable[[str, str], Tuple[str, Optional[str], int]],
        work: Optional[Path] = None, only: Optional[List[str]] = None) -> Dict[str, str]:
    """Run each axis, pushing to HF as it finishes. Returns {code: status}.

    Resumes automatically: axes already on HF are skipped. The slowest possible
    loss is one in-flight axis. Everything finished is safe the moment it lands.
    """
    from .bench import board  # deterministic scorer

    api = _hf_api()
    work = work or default_work()   # persistent volume by default
    work.mkdir(parents=True, exist_ok=True)
    print(f"  work dir (persistent): {work}", flush=True)
    result: Dict[str, str] = {}
    codes = only or list(AXES)
    for code in codes:
        name, slug = AXES[code]
        if already_done(api, code):
            result[code] = "skipped (already on HF)"
            print(f"  {name:22s} SKIP — already durable on HF", flush=True)
            continue
        try:
            bank = fetch_bank(slug, work / f"{code}.jsonl")
            board_path = work / f"board_{code}.json"
            peritem = work / f"peritem_{code}.jsonl"
            t = time.time()
            b = board(name, bank, models, ask_fn, per_item_path=str(peritem))
            board_path.write_text(json.dumps(b, indent=2))
            push_axis(api, code, board_path, peritem)          # <-- durability event
            q = [m for m in b["models"] if m["quotable"] and m["accuracy"] is not None]
            best = max((m["accuracy"] for m in q), default=None)
            result[code] = f"{b['status']} n={b['bank_items']} best={best} ({time.time()-t:.0f}s) -> HF"
            print(f"  {name:22s} {result[code]}", flush=True)
        except Exception as e:
            result[code] = f"FAILED: {type(e).__name__}: {e}"
            print(f"  {name:22s} {result[code]}", flush=True)
    return result


if __name__ == "__main__":  # pragma: no cover
    # Wiring is supplied by the pod bootstrap (ollama ask_fn + model list).
    print("durable_board: import and call run(models, ask_fn, work_dir).")
    print("axes:", ", ".join(AXES))
