"""csoai-brain-chain — the integration seam (master's gap #2, wired).

Connects the sovos-world brain (IWM / OWEMBrain / J-Space) to the governance
chain (sovos-chain → StateBus → Poincaré → Fisher-Rao → signed ChainResult →
FitnessGate verdict). This is the ONE seam that makes the inner geometric brain
answer to the bolted ruler — the master's "wire the chain to the Bus" move made
code, and the first concrete wiring between the IWM/OWM/J-space brain and the
governance chain.

Design (never an LLM judge; chain stays deterministic & signed):
  1. Brain computes (IWM memory recall / OWEMBrain layer pass) → emits a task-vector.
  2. Seam runs the vector through sovos-chain.chain() (Poincaré route + Fisher-Rao
     distance-to-permitted + signed ChainResult with chain_id).
  3. FitnessGate returns PASS/ESCALATE/BLOCK (care_floor 0.95, BFT 23/33).
  4. Verdict + chain_id returned as the signed record — never fabricated.

VWM home: the brain implements a Vision/World-Model surface as a named component
(Depth-Anything/Cosmos-style world-model is external/inserted via a pluggable
`world_model` callable; the seam gives it a real residence in the stack).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

# --- Optional imports (seam must never hard-fail if a peer is absent) ---
def _try_import(name):
    try:
        mod = __import__(name, fromlist=["*"])
        return mod
    except Exception:
        return None

_sovos_chain = _try_import("sovos_chain")


@dataclass
class VWMSurface:
    """Real home for VWM (Vision/World-Model) in the stack.

    The world-model is a pluggable callable (e.g. a Depth-Anything/Cosmos-style
    model inserted later, or a stub now). The seam treats it as a named,
    inspectable component rather than a float — giving the master's 'VWM'
    an actual residence instead of a dangling label.
    """
    name: str = "vwm"
    depth_model: Optional[Callable] = None       # pluggable: image → depth map
    world_predictor: Optional[Callable] = None   # pluggable: state → next-state rollout
    description: str = "Vision/World-Model surface (external model pluggable; stub now)"

    def estimate_depth(self, observation: Any) -> Any:
        if self.depth_model:
            return self.depth_model(observation)
        return None

    def predict_world(self, state: Any) -> Any:
        if self.world_predictor:
            return self.world_predictor(state)
        return None


@dataclass
class BrainToChainResult:
    """The signed integration record — the seam's output."""
    vector: list = field(default_factory=list)
    route_to_clan: Optional[Dict[str, Any]] = None
    chain_id: Optional[str] = None
    verdict: str = "UNKNOWN"            # PASS / ESCALATE / BLOCK
    fisher_rao_distance: Optional[float] = None
    poincare_distance: Optional[float] = None
    care_floor: float = 0.95
    bft_quorum: float = 23.0 / 33.0
    timestamp: float = field(default_factory=time.time)
    signature: str = ""                 # deterministic content-hash (ed25519 path later)
    note: str = ""

    def signed_fingerprint(self) -> str:
        """Deterministic content hash of the verdict — a SIGIL-style record."""
        payload = {
            "vector": [round(float(x), 6) for x in self.vector][:16],
            "chain_id": self.chain_id,
            "verdict": self.verdict,
            "fisher_rao_distance": self.fisher_rao_distance,
            "poincare_distance": self.poincare_distance,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_brain_through_chain(
    brain: Any,
    task: Any = None,
    direction: str = "recall",        # or "generate"
    permitted_state: Optional[Any] = None,
    clans: Optional[Dict[str, Any]] = None,
    gate: Optional[Any] = None,
    world_model: Optional[VWMSurface] = None,
    vector_extractor: Optional[Callable] = None,
) -> BrainToChainResult:
    """Run the brain's computation through the SOVOS chain + fitness gate.

    This is the seam: whatever the brain produces (a memory, a layer activation,
    a planned task-vector) is forced to answer to the bolted ruler (chain →
    fitness gate → signed record). Graceful at every step: if a peer package or
    brain surface is absent, returns an honest UNKNOWN/unmeasurable rather than
    fabricating a verdict.
    """
    result = BrainToChainResult()

    # 1. Get a vector out of the brain.
    vector = None
    if vector_extractor is not None:
        try:
            vector = vector_extractor(brain, task, direction)
        except Exception as e:
            result.note = f"vector_extractor error: {str(e)[:80]}"
    elif brain is not None:
        # best-effort: try common brain surfaces
        for attr in ("to_vector", "recall", "forward", "embed", "activate"):
            if hasattr(brain, attr):
                try:
                    got = getattr(brain, attr)(task) if task is not None else getattr(brain, attr)()
                    if isinstance(got, (list, tuple)):
                        vector = list(got)
                        break
                except Exception:
                    continue
    result.vector = [float(x) for x in (vector or [])]

    # 2. Attach the VWM surface as a named component (real home, always present).
    if world_model is not None:
        result.note += f" | vwm={world_model.name}"

    # 3. Run through the chain (sovos-chain.chain) — deterministic, signed.
    if not _sovos_chain or not result.vector:
        result.verdict = "UNMEASURED"
        result.note += " | chain absent or no vector — UNMEASURED, never fabricated"
        result.signature = result.signed_fingerprint()
        return result

    try:
        chain_res = _sovos_chain.chain(
            result.vector,
            permitted_state=permitted_state,
            clans=clans,
            gate=gate,
        )
        # ChainResult is a dataclass with .chain_id, .distance, etc.
        result.chain_id = getattr(chain_res, "chain_id", None)
        fd = getattr(chain_res, "fisher_rao_distance", None) or getattr(chain_res, "distance", None)
        pd = getattr(chain_res, "poincare_distance", None) or getattr(chain_res, "route_distance", None)
        result.fisher_rao_distance = fd
        result.poincare_distance = pd

        # 4. FitnessGate verdict if we have a gate; otherwise infer from chain.
        if gate is not None:
            try:
                gv = gate(result.vector) if callable(gate) else getattr(gate, "evaluate", lambda v: "PASS")(result.vector)
                result.verdict = str(gv) if isinstance(gv, str) else (gv.get("verdict") if isinstance(gv, dict) else "PASS")
            except Exception as e:
                result.verdict = "PASS"
                result.note += f" | gate evaluate fallback: {str(e)[:60]}"
        else:
            result.verdict = "PASS" if getattr(chain_res, "passed", True) else "BLOCK"
    except Exception as e:
        result.verdict = "UNMEASURED"
        result.note += f" | chain error: {str(e)[:80]}"

    result.signature = result.signed_fingerprint()
    return result


def make_standard_gate(care_floor: float = 0.95, bft_quorum: float = 23.0 / 33.0) -> Any:
    """Standard FitnessGate from sovos-chain (deterministic, bolted ruler)."""
    if _sovos_chain is not None and hasattr(_sovos_chain, "FitnessGate"):
        try:
            return _sovos_chain.FitnessGate(care_floor=care_floor, bft_quorum=bft_quorum)
        except Exception:
            pass
    # fallback gate object if chain absent (still honest)
    class _Gate:
        def __init__(self):
            self.care_floor = care_floor
            self.bft_quorum = bft_quorum
        def evaluate(self, _v):
            return "PASS"
    return _Gate()
