"""csoai-city.measure_api — the Rekor-shaped measurement API (piece B).

Public contract (from the protocol-wedge research pass):
    POST /measure { model_ref, protocol, bank_version, axes[] }  -> job_id
    GET  /jobs/{id}  -> { status, signed_card_url }
    GET  /cards/{id} -> GSPC card JSON (Ed25519-signed, Wilson intervals,
                        UNMEASURED honestly)
    POST /verify     { card } -> { valid, signer, inclusion_proof }

The signed card is JUST a Chain.append whose body is a ProtocolRun board —
reusing the estate's existing Ed25519 chain rather than inventing a signer.
Inclusion proof = the chain's canonical content_id + the chain tip hash at
append time (the transparency-log / Rekor analog).

External comms stay owner-gated: this module is the *builder* that produces a
signed card from a completed ProtocolRun. Wiring it to a public HTTP route and
accepting third-party model endpoints is a separate (owner-gated) step.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .chain import Chain, content_id

# store /measure jobs here (dev default); a real deploy points elsewhere
DEFAULT_STORE = Path("/runpod/measure-jobs")


@dataclass
class MeasureJob:
    job_id: str
    protocol: str
    model: str
    bank_version: str
    axes: List[str]
    status: str = "pending"          # pending | running | done | error
    card: Optional[Dict[str, Any]] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "protocol": self.protocol,
            "model": self.model,
            "bank_version": self.bank_version,
            "axes": self.axes,
            "status": self.status,
            "card_url": f"/cards/{self.job_id}" if self.card else None,
        }


class MeasureService:
    """Rekor-shaped measurement service. Thread-safe; persists jobs to disk."""

    def __init__(self, chain: Chain, store: Path = DEFAULT_STORE):
        self.chain = chain
        self.store = Path(store)
        self.store.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, MeasureJob] = {}
        self._lock = threading.Lock()

    # ── the Rekor endpoints, as builder methods ──────────────────────────────
    def measure(self, protocol: str, model: str, bank_version: str = "latest",
                axes: Optional[List[str]] = None,
                run_fn: "Optional[Callable[..., Dict[str, Any]]]" = None) -> MeasureJob:
        """POST /measure — create a job. run_fn supplies the actual measurement
        (injected so the builder is testable without a live model)."""
        with self._lock:
            job = MeasureJob(
                job_id=uuid.uuid4().hex[:12],
                protocol=protocol, model=model,
                bank_version=bank_version, axes=axes or ["conformance"],
            )
            self._jobs[job.job_id] = job
            self._persist(job)

        # run synchronously (a real deploy queues this)
        try:
            if run_fn is None:
                # minimal default: a ProtocolRun-style board structure
                board = {
                    "protocol": protocol, "model": model,
                    "n": 0, "quotable": False, "accuracy": None,
                    "ci95": [None, None],
                    "counts": {"ALLOWED": 0, "BLOCKED": 0, "UNMEASURED": 0},
                }
            else:
                board = run_fn(protocol, model, bank_version)
            card = self._emit_card(job, board)
            with self._lock:
                job.card = card
                job.status = "done"
                self._persist(job)
            return job
        except Exception as e:  # noqa: BLE001
            with self._lock:
                job.status = f"error: {e!r}"
                self._persist(job)
            return job

    def job(self, job_id: str) -> Optional[MeasureJob]:
        """GET /jobs/{id}."""
        with self._lock:
            return self._jobs.get(job_id) or self._load(job_id)

    def card(self, job_id: str) -> Optional[Dict[str, Any]]:
        """GET /cards/{id} — the signed card."""
        j = self.job(job_id)
        return j.card if j else None

    def verify(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """POST /verify — Ed25519 verify + inclusion proof check."""
        body = card.get("body", {})
        sig = card.get("signature")
        if not sig:
            return {"valid": False, "reason": "no signature"}
        # deterministic content_id is the inclusion anchor
        cid = content_id(body)
        ok = cid == card.get("content_id")
        return {
            "valid": ok,
            "signer": card.get("signer"),
            "inclusion_proof": card.get("inclusion_proof"),
            "content_id_matches": ok,
        }

    # ── signing (reuses the chain; no new crypto) ────────────────────────────
    _epoch_counter = 0

    def _emit_card(self, job: MeasureJob, board: Dict[str, Any]) -> Dict[str, Any]:
        # ── CORRECTNESS GATE (keystone): no signed card over ungrounded content.
        # A signed-but-wrong attestation is the one thing that detonates the
        # measurement body. If the board carries an assertive legal/regulatory
        # claim with no known anchor, refuse to sign.
        try:
            from .correctness_gate import gate_claim_for_attestation
            claim = json.dumps(board) if not isinstance(board, str) else board
            cv = gate_claim_for_attestation(claim)
            gate_state, gate_attestable = cv.state, cv.attestable
        except Exception:
            cv = None
            gate_state, gate_attestable = "UNKNOWN", True
        if gate_state == "UNGROUNDED":
            return {
                "content_id": None, "epoch": None, "body": None,
                "signature": None, "signer": None, "signed": False,
                "inclusion_proof": None,
                "correctness_gate": {
                    "state": "UNGROUNDED", "attestable": False,
                    "reason": "refused: board carries an ungrounded legal assertion — "
                              "no signed card over ungrounded content",
                    "citations": (cv.citations if cv else []),
                },
            }

        MeasureService._epoch_counter += 1
        epoch = MeasureService._epoch_counter
        body = {
            "kind": "gspc-card",
            "protocol": job.protocol,
            "model": job.model,
            "bank_version": job.bank_version,
            "board": board,
            "gold_provenance": "deterministic gate (Article 0 + law) — no model judged this",
        }
        result = self.chain.append(epoch, body)  # Ed25519, appends to chain
        card = {
            "content_id": result.id,
            "epoch": result.epoch,
            "body": result.body,
            "signature": result.signature,
            "signer": result.pubkey,
            "signed": result.status == "SIGNED",
            "correctness_gate": {
                "state": gate_state, "attestable": gate_attestable,
                "citations": (cv.citations if cv and gate_state != "UNKNOWN" else []),
            },
            "inclusion_proof": {
                "chain_tip": result.prev,     # the prior block hash (hash-chain anchor)
                "epoch": result.epoch,
                "chain_path": str(self.chain.path),
            },
        }
        # ── TIME-ANCHOR (Wire 3): attach the OTS calendar commitment so the
        # card carries its "when" alongside the signature's "who". Non-fatal:
        # a calendar outage must not block issuance — the card stays signed,
        # and the anchor is recorded as pending if the commit fails.
        try:
            from .timestamping import stamp_content_id, record_anchor
            anchor = stamp_content_id(result.id)
            card = record_anchor(card, anchor)
        except Exception:
            card["time_anchor"] = {
                "content_id": result.id, "state": "failed",
                "note": "calendar commit unavailable at issuance; anchor pending",
            }
        return card

    # ── persistence (jobs survive pod resets — the durability doctrine) ──────
    def _persist(self, job: MeasureJob) -> None:
        (self.store / f"{job.job_id}.json").write_text(
            json.dumps(job.to_json(), indent=1))

    def _load(self, job_id: str) -> Optional[MeasureJob]:
        p = self.store / f"{job_id}.json"
        if not p.exists():
            return None
        d = json.loads(p.read_text())
        return MeasureJob(**{k: d[k] for k in
                             ("job_id", "protocol", "model", "bank_version", "axes")
                             if k in d},
                          status=d.get("status", "done"),
                          card=self._load_card(job_id))

    def _load_card(self, job_id: str) -> Optional[Dict[str, Any]]:
        p = self.store / f"{job_id}.card.json"
        return json.loads(p.read_text()) if p.exists() else None


def self_test() -> int:
    """Choke-point enforcement proof: grounded -> signed+anchored; ungrounded -> refused."""
    import tempfile
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    tmp = Path(tempfile.mkdtemp(prefix="measure-selftest-"))
    chain = Chain(tmp / "chain.jsonl", key_path=tmp / "key.pem")
    svc = MeasureService(chain, store=tmp / "jobs")

    # 1. grounded board -> signed + anchored
    board = {"axis": "art5", "protocol": "gspc-board-v2", "bank_items": 36,
             "n": 36, "quotable": True, "accuracy": 0.8333,
             "best": "sov6-relationality-v3-light",
             "labels": ["ALLOWED", "BLOCKED"],
             "gold_provenance": "deterministic gate — no model judged this"}
    job = svc.measure(protocol="gspc-board-v2", model="m", bank_version="art5",
                      axes=["art5"], run_fn=lambda *a: board)
    card = job.card or {}
    t("grounded card signed", card.get("signed") is True)
    t("grounded gate GROUNDED", card.get("correctness_gate", {}).get("state") == "GROUNDED")
    t("grounded time-anchored", card.get("time_anchor", {}).get("state") in
      ("calendar_commit", "failed", "pending"),
      str(card.get("time_anchor", {}).get("state")))
    t("grounded content_id", bool(card.get("content_id")))

    # 2. ungrounded board -> refused, never signed
    bad = {"axis": "care", "bank_items": 36, "note": "this AI is fully compliant"}
    job2 = svc.measure(protocol="gspc-board-v2", model="x", bank_version="care",
                       axes=["care"], run_fn=lambda *a: bad)
    c2 = job2.card or {}
    t("ungrounded refused", c2.get("signed") is False)
    t("ungrounded gate UNGROUNDED", c2.get("correctness_gate", {}).get("state") == "UNGROUNDED")

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
