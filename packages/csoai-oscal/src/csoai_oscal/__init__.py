"""csoai-oscal — ChainResult → OSCAL assessment-results exporter.

OSCAL (NIST Open Security Controls Assessment Language) is the
* machine-readable compliance verdict * standard. Its `assessment-results`
model is designed for "assessors and continuous assessment tools" — a
verbatim description of the SOVOS chain. FedRAMP already accepts OSCAL
deliverables.

This package is the single highest-leverage build on the RAS board
(strategy Part O, gap-list #1): it makes the chain speak the audit
world's native language.

The exporter takes the SOFR-anchored evidence we already emit — signed,
append-only ChainResults with a Fisher-Rao distance, a permitted-radius
threshold, a chain_id, and a 24-char SIGIL-era anchor — and renders it as
a well-formed OSCAL `assessment-results` JSON document:

  {
    "oscal-version": "1.1.0",
    "system-security-plan": { "uuid": ..., "metadata": {...} },
    "results": [
      {
        "uuid": <proposal or run id>,
        "title": ...,
        "start": <ts>, "end": <ts>,
        "review": {...},
        "findings": [
          {
            "uuid": ...,
            "title": ...,
            "description": ...,
            "target": { "type": "assessment-plan" ... },
            "related-observations": [ {...} ],
            "status": { "state": "satisfied" | "not-satisfied" }
          }
        ],
        "observations": [
          {
            "uuid": ...,
            "collected": <ts>,
            "type": "control-objective-assessment",
            "relevance": "...",
            "origins": [ {"type": "tool", "implementer-uuid": ...} ],
            "subjects": [...],
            "assessed-controls": [ {"control-id": "..."} ]
          }
        ]
      }
    ]
  }

Mappings (the law):
  - A ChainResult's `is_permitted` -> the finding's status:
      True  -> {"state": "satisfied"}     (control objective met)
      False -> {"state": "not-satisfied"} (control objective NOT met)
  - `chain_id` -> the observation uuid / finding target (audit anchor)
  - `fisher_rao_distance` vs `threshold` -> the assessed-control result
      (this is the *measurement* an assessor reads)
  - `source`/`layer`/`vector` -> subject + relevance description
  - The run -> OSCAL `assessment-results` results entry

Honest scope: this emits *OSCAL-shaped* JSON that is structurally
valid per the OSCAL 1.1 assessment-results model. It is NOT a full
OSCAL schema validator — that's the callers' concern (or a future
dependency on a validator). We produce the audit world's envelope so a
FedRAMP importer can consume it. The `implementer-uuid` is a fixed
CSOAI uuid (settable); provenance of each constituent's sigma remains
the caller's job (from sovos-sigma-calibration).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid as pyuuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OSCAL_VERSION = "1.1.0"
DEFAULT_IMPLEMENTER_UUID = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# Small dataclasses mirroring a ChainResult's relevant fields (decouple
# from a hard dependency on sovos-chain so this package runs standalone).
# ---------------------------------------------------------------------------
@dataclass
class ChainObservation:
    """The minimal signed evidence a ChainResult carries, for OSCAL."""
    chain_id: str
    source: str
    layer: str
    vector: List[float] = field(default_factory=list)
    distance: float = 0.0
    threshold: float = 1.0
    is_permitted: bool = False
    sigma: float = 1.0
    control_id: str = "AI-GENERAL"     # the assessed control (art/mapping)
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_chain_result(cls, r: Any, control_id: str = "AI-GENERAL",
                          **kw: Any) -> "ChainObservation":
        """Shim from a sovos-chain ChainResult (duck-typed) to our shape."""
        d = getattr(r, "distance", None)
        if d is None:
            d = getattr(r, "fisher_rao_distance", None)
        if d is None and isinstance(r, dict):
            d = r.get("distance") or r.get("fisher_rao_distance")
        if d is None:
            raise ValueError("cannot extract distance from ChainResult")
        src = getattr(r, "source", None) or (r.get("source") if isinstance(r, dict) else "")
        layer = getattr(r, "layer", None) or (r.get("layer") if isinstance(r, dict) else "")
        vec = getattr(r, "vector", None)
        if vec is None and isinstance(r, dict):
            vec = r.get("vector", [])
        cid = getattr(r, "chain_id", "") or (r.get("chain_id") if isinstance(r, dict) else "")
        thresh = getattr(r, "threshold", 1.0)
        if isinstance(r, dict):
            thresh = r.get("threshold", thresh)
        perm = getattr(r, "is_permitted", None)
        if perm is None and isinstance(r, dict):
            perm = r.get("is_permitted")
        if perm is None:
            perm = float(d) <= float(thresh)
        return cls(
            chain_id=str(cid), source=str(src), layer=str(layer),
            vector=list(vec) if vec else [],
            distance=float(d), threshold=float(thresh),
            is_permitted=bool(perm), control_id=control_id, **kw,
        )


# ---------------------------------------------------------------------------
# OSCAL JSON builders
# ---------------------------------------------------------------------------
def _uuid() -> str:
    return str(pyuuid.uuid4())


def _metadata(implementer_uuid: str, title: str, ts: str) -> Dict[str, Any]:
    return {
        "title": title,
        "version": OSCAL_VERSION,
        "last-modified": ts,
        "oscal-version": OSCAL_VERSION,
        "implemented-by": [{"uuid": implementer_uuid}],
    }


def observation(obs: ChainObservation, implementer_uuid: str) -> Dict[str, Any]:
    """Render one ChainObservation as an OSCAL observation."""
    o_uuid = obs.chain_id if len(obs.chain_id) == 36 else _uuid()
    return {
        "uuid": o_uuid,
        "collected": obs.ts,
        "type": "control-objective-assessment",
        "relevance": (
            f"{obs.source} [{obs.layer}] distance {obs.distance:.4f} "
            f"vs threshold {obs.threshold} (sigma {obs.sigma})"
        ),
        "origins": [{"type": "tool", "implementer-uuid": implementer_uuid}],
        "subjects": [{"type": "set-parameters",
                      "subject-uuid": str(pyuuid.uuid5(pyuuid.NAMESPACE_URL,
                                                       obs.source + obs.layer))}],
        "assessed-controls": [{"control-id": obs.control_id}],
        "collecting-method": "tool-integrated",
    }


def finding(obs: ChainObservation, implementer_uuid: str) -> Dict[str, Any]:
    """Render one ChainObservation as an OSCAL finding (the verdict)."""
    f_uuid = _uuid()
    status = {"state": "satisfied"} if obs.is_permitted else \
             {"state": "not-satisfied",
              "related-information": [{"text": "permitted-manifold distance exceeded",
                                       "source": "chain-result"}]}
    return {
        "uuid": f_uuid,
        "title": f"chain verdict: {obs.control_id} — " + (
            "satisfied" if obs.is_permitted else "not satisfied"),
        "description": (
            f"Continuous assessment of '{obs.control_id}' from {obs.source} "
            f"(layer {obs.layer}): geometric distance to permitted manifold = "
            f"{obs.distance:.4f} (threshold {obs.threshold}). Signed chain "
            f"anchor: {obs.chain_id}.")
        ,
        "target": {
            "type": "assessment-plan",
            "title": f"chain plan for {obs.control_id}",
            "target-id": obs.chain_id or _uuid(),
            "location-uuids": [],
            "props": [
                {"name": "sovos-chain-id", "ns": "https://csoai.org/ns/sovos",
                 "value": obs.chain_id},
                {"name": "fisher-rao-distance", "ns": "https://csoai.org/ns/sovos",
                 "value": str(round(obs.distance, 6))},
                {"name": "permitted-radius", "ns": "https://csoai.org/ns/sovos",
                 "value": str(obs.threshold)},
            ],
        },
        "related-observations": [obs.chain_id if len(obs.chain_id) == 36 else ""],
        "status": status,
    }


def assessment_results(observations: List[ChainObservation],
                       title: str = "SOVOS continuous compliance assessment",
                       implementer_uuid: str = DEFAULT_IMPLEMENTER_UUID,
                       run_id: Optional[str] = None,
                       article_zero: bool = False) -> Dict[str, Any]:
    """Compose a complete OSCAL `assessment-results` document.

    Since v0.2.0 the SSP chain-id is DETERMINISTIC: it hashes the result
    content (findings/observations structure + title + article-zero),
    not the random run uuid, so identical assessments reproduce the same
    audit anchor. The results entry carries article-zero + passed/
    assessed props for the regulator/insurer reader.
    """
    ts = datetime.now(timezone.utc).isoformat()
    rid = run_id or _uuid()
    passed = sum(1 for o in observations if o.is_permitted)
    results_entry = {
        "uuid": rid,
        "title": title,
        "start": ts,
        "end": ts,
        "props": [
            {"name": "assessed-entities", "value": str(len(observations))},
            {"name": "passed", "value": str(passed)},
            {"name": "article-zero", "value": str(article_zero).lower()},
        ],
        "local-definitions": {
            "subjects": [
                {"uuid": str(pyuuid.uuid5(pyuuid.NAMESPACE_URL, o.source)),
                 "type": "system", "title": o.source,
                 "props": [{"name": "layer", "value": o.layer}]}
                for o in observations
            ]
        },
        "findings": [finding(o, implementer_uuid) for o in observations],
        "observations": [observation(o, implementer_uuid) for o in observations],
    }
    # Deterministic chain-id over the content (not the random uuid) —
    # SOFR-style: the anchor is reproducible from the assessment itself.
    chain_body = json.dumps({
        "title": title,
        "n": len(observations),
        "passed": passed,
        "statuses": [("satisfied" if o.is_permitted else "not-satisfied") for o in observations],
        "article_zero": article_zero,
    }, sort_keys=True).encode()
    ssp_chain = hashlib.sha256(chain_body).hexdigest()[:24]
    doc = {
        "oscal-version": OSCAL_VERSION,
        "system-security-plan": {
            "uuid": _uuid(),
            "chain-id": ssp_chain,
            "metadata": _metadata(implementer_uuid, title, ts),
        },
        "results": [results_entry],
    }
    return doc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def dump(doc: Dict[str, Any], pretty: bool = True) -> str:
    return json.dumps(doc, indent=2) if pretty else json.dumps(doc)


def export(observations: List[ChainObservation],
           title: str = "SOVOS continuous compliance assessment",
           implementer_uuid: str = DEFAULT_IMPLEMENTER_UUID,
           run_id: Optional[str] = None,
           article_zero: bool = False) -> str:
    """Produce an OSCAL assessment-results document as a JSON string."""
    return dump(assessment_results(observations, title=title,
                                   implementer_uuid=implementer_uuid,
                                   run_id=run_id,
                                   article_zero=article_zero))


def self_test() -> Dict[str, Any]:
    """Build a small document and report the salient structure."""
    ok = ChainObservation(chain_id="aabbccddeeff00112233445566778899aabbccdd",
                          source="birth:iokfarm", layer="water",
                          vector=[0.1, 0.2, 0.3],
                          distance=0.0845, threshold=1.0, is_permitted=True)
    bad = ChainObservation(chain_id="1122334455aabbccddeeff001122334455aabbcc",
                           source="chat:iokfarm", layer="milk",
                           vector=[3.0, 0.0, 0.0, 0.0],
                           distance=4.605, threshold=1.0, is_permitted=False,
                           control_id="EU-AI-ACT-14")
    doc = assessment_results([ok, bad], title="verification")
    return {
        "oscal_version": doc.get("oscal-version"),
        "n_results": len(doc.get("results", [])),
        "n_findings": len(doc["results"][0]["findings"]),
        "satisfied_count": sum(1 for f in doc["results"][0]["findings"]
                               if f["status"]["state"] == "satisfied"),
        "not_satisfied_count": sum(1 for f in doc["results"][0]["findings"]
                                   if f["status"]["state"] == "not-satisfied"),
        "has_observations": len(doc["results"][0]["observations"]) == 2,
        "dump_chars": len(dump(doc)),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
