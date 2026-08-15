"""BENCH — score a GSPC item bank across a fleet, deterministically.

The city measures the swarm axis. Every other axis already has an authored item
bank with an `expected` label; what they lack is a BOARD — the same bank put to
several models and graded by rule.

Grading is exact-label, and the label set comes from the bank itself rather than
being hardcoded, so a bank with new labels does not silently grade as all-wrong.
An answer that does not name exactly one label is UNPARSED, and unparsed counts
as incorrect — never dropped, because a model that cannot state an answer has
still failed to state one.

Canary rows (`_canary`) are detected and EXCLUDED from every score. They exist to
catch contamination and must never enter a number.

Nothing is quoted below 30 usable items. `quotable` is computed, never asserted,
and a board under the floor reports its accuracy as None rather than as a small
number that will be screenshotted without its caveat.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

MIN_N = 30


def load_bank(path: str | Path) -> Tuple[List[Dict[str, Any]], int]:
    """Return (real items, canary count). Canaries never reach a score."""
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    # A canary is any row flagged by the _canary key, OR one whose label/text is a
    # canary sentinel — some banks marked canaries only by expected=="CANARY" or a
    # __CANARY__ string, which leaked as a scored label until caught (gspc-swarm).
    def is_canary(r):
        if "_canary" in r: return True
        if str(r.get("expected","")).upper() == "CANARY": return True
        return any("__CANARY__" in str(v) for v in r.values() if isinstance(v, str))
    real = [r for r in rows if not is_canary(r)]
    return real, len(rows) - len(real)


def label_set(items: List[Dict[str, Any]]) -> List[str]:
    """The bank declares its own labels. Hardcoding them is how a bank silently
    grades as all-wrong after someone adds a category."""
    return sorted({str(r["expected"]) for r in items if r.get("expected")})


# Banks name the item text differently — scenario / request / operation / item /
# tool / case / text. The label is always `expected`. Resolve the text field per
# row rather than assuming one name, so a differently-shaped bank scores instead
# of crashing the whole parallel run with KeyError.
TEXT_FIELDS = ("item", "scenario", "request", "operation", "tool", "case", "text",
               "question", "input", "prompt")

def item_text(item: Dict[str, Any]) -> str:
    for k in TEXT_FIELDS:
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v
    # last resort: the longest string value that is not the label
    cands = [v for k, v in item.items()
             if isinstance(v, str) and k not in ("expected", "label", "gold", "answer",
                                                 "category", "anchor", "note", "source")]
    return max(cands, key=len) if cands else ""

def prompt_for(item: Dict[str, Any], labels: List[str]) -> str:
    return (f"{item_text(item)}\n\n"
            f"Answer with EXACTLY ONE of these labels and nothing else: {', '.join(labels)}.")


def parse(answer: str, labels: List[str]) -> Optional[str]:
    """Exactly one label, or None. Ambiguity is unparsed, not a coin flip."""
    if not answer:
        return None
    up = answer.upper()
    hits = [l for l in labels if re.search(r"\b" + re.escape(l.upper()) + r"\b", up)]
    return hits[0] if len(hits) == 1 else None


def wilson(k: int, n: int, z: float = 1.959964) -> Optional[Tuple[float, float]]:
    if n < MIN_N:
        return None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


@dataclass
class ModelBoard:
    model: str
    n: int
    correct: int
    unparsed: int
    accuracy: Optional[float]
    ci95: Optional[List[float]]
    quotable: bool
    note: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def score_model(model: str, items: List[Dict[str, Any]], labels: List[str],
                ask_fn: Callable[[str, str], Tuple[str, Optional[str], int]],
                sink: Optional[List[Dict[str, Any]]] = None) -> ModelBoard:
    """Score one model. `sink` collects per-item rows — the training signal.

    The board is the aggregate; what a distilled model can actually learn from is
    WHICH item each model got wrong and what it answered instead. Emitting only
    the aggregate throws that away, and re-running to recover it costs GPU hours.
    """
    correct = unparsed = usable = 0
    for it in items:
        text, err, _ = ask_fn(model, prompt_for(it, labels))
        got = None if err else parse(text, labels)
        if sink is not None:
            sink.append({
                "axis_item": it.get("anchor") or item_text(it)[:80],
                "item": item_text(it), "category": it.get("category"),
                "expected": it.get("expected"), "model": model,
                # Severity propagates from bank item → per-item row so tail.py
                # can severity-weight (C3, handoff §7). None on banks without it.
                "severity": it.get("severity"),
                "severity_basis": it.get("severity_basis"),
                "raw": (text or "")[:400], "parsed": got,
                "correct": (got == str(it["expected"])) if got else False,
                "unparsed": got is None and not err,
                "transport_error": err,
            })
        if got is None:
            # A transport failure is OURS and is not usable evidence about the
            # model; an unreadable answer is THEIRS and counts as incorrect.
            if err and err.startswith("TRANSPORT"):
                continue
            unparsed += 1
            usable += 1
            continue
        usable += 1
        if got == str(it["expected"]):
            correct += 1
    acc = (correct / usable) if usable else None
    ci = wilson(correct, usable) if usable else None
    quot = bool(usable >= MIN_N)
    return ModelBoard(
        model=model, n=usable, correct=correct, unparsed=unparsed,
        accuracy=(round(acc, 4) if (acc is not None and quot) else None),
        ci95=([round(x, 4) for x in ci] if ci else None),
        quotable=quot,
        note=(None if quot else f"usable n={usable} < {MIN_N} — no score quoted"),
    )


def board(axis: str, bank_path: str | Path, models: List[str],
          ask_fn: Callable[[str, str], Tuple[str, Optional[str], int]],
          per_item_path: Optional[str | Path] = None) -> Dict[str, Any]:
    items, canaries = load_bank(bank_path)
    labels = label_set(items)
    per_item: List[Dict[str, Any]] = []
    rows = [score_model(m, items, labels, ask_fn, sink=per_item) for m in models]
    quotable_rows = [r for r in rows if r.quotable and r.accuracy is not None]
    best = max(quotable_rows, key=lambda r: r.accuracy) if quotable_rows else None

    if per_item_path:
        Path(per_item_path).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in per_item) + "\n", encoding="utf-8")

    return {
        "kind": "gspc.board",
        "axis": axis,
        "bank_items": len(items),
        "canaries_excluded": canaries,
        "labels": labels,
        "majority_baseline": round(
            max(sum(1 for i in items if str(i["expected"]) == l) for l in labels) / len(items), 4
        ) if items else None,
        "models": [r.to_dict() for r in rows],
        "best": (best.model if best else None),
        "status": ("MEASURED" if quotable_rows else "UNMEASURED"),
        "status_note": (
            None if quotable_rows else
            f"no model reached {MIN_N} usable items; the axis stays UNMEASURED"),
        "per_item_count": len(per_item),
        "method": ("unparsed counted incorrect · transport failures excluded as ours · "
                   "canaries excluded · deterministic exact-label grading, no model judges "
                   "another model · nothing quoted below usable n>=30"),
    }
