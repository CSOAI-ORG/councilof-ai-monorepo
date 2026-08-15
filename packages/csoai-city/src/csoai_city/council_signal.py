"""csoai-city.council_signal — Council Signal (Play A).

A continuous, lawful auto-compliance scanner over PUBLISHED AI artifacts
(model-card facts, HF metadata, transparency reporting) that emits a compact
Ed25519-signed per-entity state record and a DRIFT line when a re-scan differs.

Legal posture (from the synthesis pass):
  * scan PUBLISHED artifacts ONLY (public C2PA manifests, model cards, metadata)
    — hiQ v. LinkedIn / Van Buren footing. NEVER private APIs without consent.
  * "measured/signed state record", never "we simulate your regulation" and
    never ISO-17024/17065-accredited certification.

Design:
  * ingest a set of artifact facts (each keyed to a GSPC axis, carrying a
    decimal measurement + expectation)
  * compute per-axis scores, aggregate the SOV signal (reusing
    sovos_signal_index.aggregate_sov_signal)
  * persist a signed state record per entity via the existing Chain
  * on a later scan of the SAME entity, compute drift vs stored state and emit
    a tamper-evident drift line (the Vanta/Drata continuous-monitoring analog
    applied to third-party published AI metadata).
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chain import Chain, content_id

# Optional heavy dependency — SOV signal aggregation
try:
    from sovos_signal_index import aggregate_sov_signal  # type: ignore
    HAS_SIGNAL = True
except Exception:  # pragma: no cover
    aggregate_sov_signal = None
    HAS_SIGNAL = False


@dataclass
class ArtifactFact:
    """One measurement of a published artifact, keyed to a GSPC axis.
    `score` in [0,1] (higher = more compliant/healthy), `expectation` is a
    threshold used for a PASS/WATCH/FAIL verdict."""
    axis: str
    label: str
    score: float
    expectation: float = 0.5
    source: str = ""

    def verdict(self) -> str:
        return "FAIL" if self.score < self.expectation * 0.5 else (
            "WATCH" if self.score < self.expectation else "PASS")


class CouncilSignal:
    """Per-entity scanner + signed state + drift."""

    def __init__(self, chain: Chain, store: Path = Path("/runpod/council-signal")):
        self.chain = chain
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self._epoch = 0

    def scan(self, entity: str, facts: List[ArtifactFact],
             version: str = "1") -> Dict[str, Any]:
        """Scan `entity`'s published artifacts, aggregate signal, sign state,
        and return a drift report vs any previously stored state."""
        self._epoch += 1
        body = {
            "kind": "council-signal.state",
            "entity": entity,
            "version": version,
            "facts": [{"axis": f.axis, "label": f.label, "score": round(f.score, 4),
                       "expectation": f.expectation, "verdict": f.verdict(),
                       "source": f.source} for f in facts],
            "aggregated": self._aggregate([f.score for f in facts]),
            "gold_provenance": "deterministic measurement of published artifacts — no model judged this",
        }
        # sign through the chain
        cr = self.chain.append(self._epoch, body)
        record = {
            "entity": entity,
            "version": version,
            "content_id": cr.id,
            "signed": cr.status == "SIGNED",
            "signature": cr.signature,
            "body": body,
            "detector": f"council-signal v1",
        }
        # drift vs stored prior state of the same entity
        prev = self._load_entity(entity)
        drift = []
        if prev is not None:
            drift = self._diff(entity, prev, body)
        # persist new state
        self._save_entity(entity, version, record)
        return {"record": record, "drift": drift, "is_first_scan": prev is None}

    # ── helpers ──────────────────────────────────────────────────────────────
    def _aggregate(self, scores: List[float]) -> Dict[str, Any]:
        if not scores:
            return {"n": 0, "mean": None}
        if HAS_SIGNAL and aggregate_sov_signal is not None:
            try:
                # Real wiring: raw scores -> ConstituentScore -> SOV signal index.
                # (Formerly fed {"score":...} dicts into a distance-based index —
                #  a silent shape mismatch. attestation_registry fixes that.)
                from .attestation_registry import from_accuracy, aggregate_attestation_scores
                cons = [from_accuracy(f"axis{i}", s, 128) for i, s in enumerate(scores)]
                res = aggregate_attestation_scores(cons)
                return {"n": len(scores), "signal": res}
            except Exception:
                pass
        return {"n": len(scores), "mean": round(sum(scores) / len(scores), 4)}

    def _diff(self, entity: str, prev_body: Dict[str, Any],
              new_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        old = {f["label"]: f for f in prev_body.get("facts", [])}
        new = {f["label"]: f for f in new_body.get("facts", [])}
        changes = []
        for label in new:
            if label in old and abs(old[label]["score"] - new[label]["score"]) > 0.001:
                changes.append({
                    "label": label,
                    "axis": new[label]["axis"],
                    "before": old[label]["score"],
                    "after": new[label]["score"],
                    "delta": round(new[label]["score"] - old[label]["score"], 4),
                })
        # additions / removals as drift too
        for label in set(new) - set(old):
            changes.append({"label": label, "axis": new[label]["axis"],
                            "action": "added"})
        for label in set(old) - set(new):
            changes.append({"label": label, "axis": old[label]["axis"],
                            "action": "removed"})
        return changes

    def _load_entity(self, entity: str) -> Optional[Dict[str, Any]]:
        p = self.store / f"{_slug(entity)}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return d.get("body")

    def _save_entity(self, entity: str, version: str, record: Dict[str, Any]) -> None:
        (self.store / f"{_slug(entity)}.json").write_text(
            json.dumps(record, default=str, indent=1))


def _slug(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
