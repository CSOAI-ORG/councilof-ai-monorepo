"""THE BOLTED RULER — the judge surfaces, and proof they did not move.

Part AV doctrine: the generator may evolve as cleverly and autonomously as it
likes; the ruler stays bolted to the wall. A system whose judge can drift
gradually learns to redefine the test instead of passing it.

Aspiration is not a control, so this module makes it mechanical. The judge
surfaces are fingerprinted, the fingerprint is pinned in `JUDGE.lock` alongside
who ratified it, and every run verifies the two match. If they do not, the run
does not quietly continue with a different ruler — the board is marked
`valid: false` and says the judge drifted.

WHAT IS A JUDGE SURFACE
  * `law.py` in full — the gate: Article 0 wiring plus EU AI Act Art 5(1)(a)-(h)
  * `CANARIES` — the positive control that proves the gate fires
  * `PARAPHRASE_PROBES` — the recall probe that measures what the gate misses

WHAT IS NOT
  The grammar, the briefs, the goals, the probe *goal wording*, the citizen
  population, the models. All generator-side: evolve them freely. Changing how a
  question is asked is fair game; changing what counts as a correct answer is not.

RE-RATIFYING
  A legitimate judge change (say, a counsel-approved verb-class mapping) is not
  forbidden — it is *gated*. Update the lock deliberately, with a name and a
  reason, and the diff is visible in git forever. What cannot happen is the ruler
  moving without anyone noticing.

This module deliberately offers no `--force`. `write_lock()` requires a ratifier
and a reason, so a lock cannot be regenerated as a silent side effect of a run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

LOCK_NAME = "JUDGE.lock"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def judge_fingerprint() -> Dict[str, str]:
    """Hash every judge surface. Imported lazily so law.py stays the single source."""
    from . import law
    from . import arena

    law_src = Path(law.__file__).read_bytes()
    return {
        "law.py": _sha(law_src),
        "CANARIES": _sha(_canon(arena.CANARIES)),
        "PARAPHRASE_PROBES": _sha(_canon(
            [(k, d, a) for k, d, a in arena.PARAPHRASE_PROBES])),
    }


def combined(fp: Dict[str, str]) -> str:
    return _sha(_canon(fp))[:24]


def lock_path(pkg_dir: Optional[Path] = None) -> Path:
    return (pkg_dir or Path(__file__).resolve().parent) / LOCK_NAME


def read_lock(pkg_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    p = lock_path(pkg_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_lock(ratified_by: str, reason: str, when: str,
               pkg_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Pin the current judge surfaces. Requires a named ratifier and a reason.

    There is no unattended path to this function: a run never calls it. Moving the
    ruler is a deliberate, attributed act that leaves a diff.
    """
    if not ratified_by.strip() or not reason.strip() or not when.strip():
        raise ValueError("ratified_by, reason and when are all required to move the ruler")
    fp = judge_fingerprint()
    lock = {
        "kind": "csoai-city.judge-lock",
        "surfaces": fp,
        "judge_id": combined(fp),
        "ratified_by": ratified_by.strip(),
        "reason": reason.strip(),
        "ratified_at": when.strip(),
        "doctrine": ("Part AV — the generator evolves, the judge does not. Legal-semantic "
                     "mappings never auto-promote; they queue for counsel."),
    }
    lock_path(pkg_dir).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def verify(pkg_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Compare the live judge against the ratified one. Reports; never repairs."""
    fp = judge_fingerprint()
    now = combined(fp)
    lock = read_lock(pkg_dir)

    if lock is None:
        return {
            "ratified": False, "drift": True, "judge_id": now, "locked_judge_id": None,
            "changed_surfaces": sorted(fp),
            "note": ("no JUDGE.lock — the judge has never been ratified, so nothing can attest "
                     "that this ruler is the one previous results were measured against"),
        }

    locked = lock.get("surfaces", {})
    changed = sorted(k for k in set(fp) | set(locked) if fp.get(k) != locked.get(k))
    drift = bool(changed)
    return {
        "ratified": True,
        "drift": drift,
        "judge_id": now,
        "locked_judge_id": lock.get("judge_id"),
        "ratified_by": lock.get("ratified_by"),
        "ratified_at": lock.get("ratified_at"),
        "reason": lock.get("reason"),
        "changed_surfaces": changed,
        "note": ("judge surfaces match the ratified lock" if not drift else
                 f"JUDGE DRIFT — {', '.join(changed)} changed since ratification. Results from "
                 "this run were NOT measured against the ratified ruler and must not be compared "
                 "with runs that were. Re-ratify deliberately, or restore the judge."),
    }


if __name__ == "__main__":  # pragma: no cover
    import sys
    v = verify()
    print(json.dumps(v, indent=2))
    sys.exit(0 if v.get("ratified") and not v.get("drift") else 1)
