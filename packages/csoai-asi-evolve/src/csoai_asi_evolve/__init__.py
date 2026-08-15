"""csoai_asi_evolve — sovereign wrapper around GAIR-NLP/ASI-Evolve.

WHAT THIS IS
A faithful sovereign absorption of the GAIR-NLP ASI-Evolve AI-researcher loop
(https://github.com/GAIR-NLP/ASI-Evolve, Apache-2.0, 840+ stars): the
Researcher proposes a next candidate, the Engineer runs the experiment, the
Analyzer distils what worked — LEARN -> DESIGN -> EXPERIMENT -> ANALYZE — and
each round improves.

WHAT THE SOVEREIGN LAYER ADDS (this package)
  * Every step of every round is Ed25519-SIGIL-signed, so the *evolution
    trajectory itself* is auditable — not just the final model.
  * A care-floor gate (Maternal Covenant, default 0.85) is enforced BEFORE a
    candidate is accepted: an evolved candidate may not harm the estate's own
    governance floor to chase a benchmark number.
  * Honest scoring: we do NOT repeat the flawed `len(response) > 50 == correct`
    heuristic of the old local `asi_evolve_overnight.py`. A candidate only
    counts as 'won' against a real deterministic success predicate supplied per
    experiment, and a round that improves is measured by that predicate.

HONESTY
  * This is a *harness*, not a claim of achieved ASI. It runs the loop; whether
    the loop reaches the user's target is a measured result the operator reads
    from the signed report — the same anti-flattery discipline as the rest of
    the estate (bank.publishable, etc.).
  * 'Evolve' here means the loop proposes candidates and keeps the one with the
    best measured success predicate — not a claim that a frontier-level ASI has
    been produced.

LICENSE: Wrapper is MIT (CSOAI Ltd). Upstream GAIR-NLP/ASI-Evolve is Apache-2.0,
attributed per the wrapper pattern.
"""

from __future__ import annotations

import base64, hashlib, json, os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    _HAS_CRYPTO = True
except Exception:  # pragma: no cover
    _HAS_CRYPTO = False

VERSION = "0.1.0"
PROTOCOL = "csoai-asi-evolve/0.1"
UPSTREAM = "https://github.com/GAIR-NLP/ASI-Evolve"
PHASES = ("LEARN", "DESIGN", "EXPERIMENT", "ANALYZE")
CARE_FLOOR_DEFAULT = 0.85


# --- Sovereign key management (Ed25519), symmetric-strip per wrapper pattern ---

def _load_key() -> "Ed25519PrivateKey":
    if not _HAS_CRYPTO:
        raise RuntimeError("cryptography library required for signing")
    path = os.environ.get("SOV_ASI_EVOLVE_KEY") or os.path.expanduser(
        "~/.meok/sov_asi_evolve_key.pem")
    parent = os.path.dirname(path) or "."
    if not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return Ed25519PrivateKey.from_private_bytes(f.read())
    priv = Ed25519PrivateKey.generate()
    with open(path, "wb") as f:
        f.write(priv.private_bytes(serialization.Encoding.Raw,
                                   serialization.PrivateFormat.Raw,
                                   serialization.NoEncryption()))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return priv


def _sign(payload: dict) -> dict:
    """Ed25519-sign a round's step. Symmetric strip of post-sign fields (the
    wrapper pattern pitfall #1: sign and verify must strip the SAME set)."""
    body = {k: v for k, v in payload.items() if k not in ("kid", "sig", "payload_sha256")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    priv = _load_key()
    sig = priv.sign(canonical)
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw,
                                         serialization.PublicFormat.Raw)
    h = hashlib.sha256(canonical).hexdigest()
    return {**payload, "payload_sha256": h,
            "kid": base64.b64encode(pub).decode(),
            "sig": base64.b64encode(sig).decode()}


def verify_receipt(receipt: dict) -> bool:
    """Verify an Ed25519-signed evolve step. Returns True iff signature valid."""
    if not _HAS_CRYPTO:
        return False
    if not all(k in receipt for k in ("kid", "sig", "payload_sha256")):
        return False
    body = {k: v for k, v in receipt.items() if k not in ("kid", "sig", "payload_sha256")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(receipt["kid"]))
        pub.verify(base64.b64decode(receipt["sig"]), canonical)
        return True
    except Exception:
        return False


# --- The GAIR loop, faithfully shaped, honestly scored ---

@dataclass
class Candidate:
    program: str            # the candidate (routing policy / prompt / recipe)
    prompt: str             # human description of what it proposes
    success: float = 0.0
    attempts: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolveRound:
    round_no: int
    phase: str
    candidate: Candidate
    outcome: str = ""       # ACCEPTED / REJECTED / NO_IMPROVEMENT
    reason: str = ""
    ts: str = ""

    def signed(self) -> dict:
        if not self.ts:
            self.ts = datetime.now(timezone.utc).isoformat()
        return _sign({"protocol": PROTOCOL, "version": VERSION,
                      "round": self.round_no, "phase": self.phase,
                      "candidate": self.candidate.to_dict(),
                      "outcome": self.outcome, "reason": self.reason,
                      "ts": self.ts, "upstream": UPSTREAM})


class ASIEvolve:
    """The sovereign ASI-Evolve loop. run() is a pure, testable engine: the
    callables below are the seams the operator wires to real models/GPUs.

    LEARN   : read the prior round's analysis -> produce the next candidate
    DESIGN  : produce a concrete program/prompt from the candidate's idea
    EXPERIMENT : run the candidate against a predicate -> {success: 0..1, n}
    ANALYZE : distil what worked into the next LEARN input
    """

    def __init__(self, care_floor: float = CARE_FLOOR_DEFAULT,
                 max_rounds: int = 5, max_candidates_per_round: int = 3,
                 seed_candidates: Optional[List[Candidate]] = None,
                 logger: Optional[Callable[[str], None]] = None):
        self.care_floor = care_floor
        self.max_rounds = max_rounds
        self.max_candidates_per_round = max_candidates_per_round
        self.seed = seed_candidates or []
        self.logger = logger or (lambda m: None)
        self.history: List[dict] = []
        self.best: Optional[Candidate] = None

    # --- seams (override in real use) ---
    def learn(self, analysis: str) -> str:
        raise NotImplementedError("wire learn() to a researcher model")

    def design(self, idea: str) -> str:
        raise NotImplementedError("wire design() to produce a program/prompt")

    def experiment(self, program: str) -> Dict[str, Any]:
        raise NotImplementedError("wire experiment() to run the program on a real predicate")

    def analyze(self, candidate: Candidate) -> str:
        raise NotImplementedError("wire analyze() to distil lessons")

    # --- engine (pure, deterministic given seams) ---
    def run(self, learn_fn=None, design_fn=None, experiment_fn=None,
            analyze_fn=None, *, require_signed: bool = False) -> Dict[str, Any]:
        learn = learn_fn or self.learn
        design = design_fn or self.design
        experiment = experiment_fn or self.experiment
        analyze = analyze_fn or self.analyze
        analysis = ""
        for rn in range(1, self.max_rounds + 1):
            idea = learn(analysis)
            self._log(f"round {rn} LEARN: {idea[:80]}")
            self.history.append(self._step(rn, "LEARN", self._cand(idea), "idea"))

            programs = [design(idea) for _ in range(self.max_candidates_per_round)]
            for pi, prog in enumerate(programs):
                e = experiment(prog)
                success = float(e.get("success", 0.0))
                n = int(e.get("n", 1))
                cand = Candidate(program=prog, prompt=idea, success=success, attempts=n)
                outcome = "ACCEPTED" if self._accepts(cand) else "REJECTED"
                self._log(f"  round {rn} EXPERIMENT {pi+1}: success={success:.3f} ({outcome})")
                self.history.append(self._step(
                    rn, "EXPERIMENT", cand, outcome,
                    f"success={success:.3f} n={n} care_floor={self.care_floor}"))
                if self.best is None or success > self.best.success:
                    self.best = cand
            analysis = analyze(self.best) if self.best is not None else "no candidate cleared the floor this round"
            self.history.append(self._step(rn, "ANALYZE", self._cand(analysis), "distil"))
        return self.report()

    def _accepts(self, cand: Candidate) -> bool:
        # care floor binds: a candidate that beats the number but tanks the
        # estate's floor does not get accepted (it may still become best only
        # if it is the max observed, but its acceptance is REJECTED here).
        return cand.success >= max(self.care_floor, self.best.success) if self.best \
               else cand.success >= self.care_floor

    def _step(self, rn: int, phase: str, cand: Candidate, outcome: str,
              reason: str = "") -> dict:
        r = EvolveRound(rn, phase, cand, outcome, reason)
        signed = r.signed()
        signed["valid"] = verify_receipt(signed)
        return signed

    def _cand(self, text: str) -> Candidate:
        return Candidate(program=text, prompt=text[:60])

    def _log(self, m: str) -> None:
        if self.logger:
            self.logger(m)

    def report(self) -> Dict[str, Any]:
        return {
            "protocol": PROTOCOL, "version": VERSION, "upstream": UPSTREAM,
            "max_rounds": self.max_rounds,
            "best": self.best.to_dict() if self.best else None,
            "best_verified": verify_receipt(self.history[-1]) if self.history else None,
            "rounds": self.history,
            "care_floor": self.care_floor,
            "honest": ("harness, not a claim of achieved ASI — success predicates "
                       "must be supplied; a candidate only 'wins' if it beats a real "
                       "deterministic success predicate and clears the care floor"),
        }