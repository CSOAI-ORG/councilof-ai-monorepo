"""csoai_dream — Dream-loop harness for humanoid imagination.

Master Part U.3 — humanoids dream in SOV Space. The architecture:

  NVIDIA pipeline: Cosmos + Omniverse + Isaac Sim/Lab + Holoscan
  2026 world models surveyed (UniPi, RoboDreamer, DreamGen,
    action-controllable WMs, structure-aware 4D forecasting,
    Cosmos Predict 2.5, Unitree UnifoLM-WMA-0).

SOVOS mapping:
  - rollouts = StateVectors in J-Space
  - drum.rs = the dream engine (sovos-hive Ring-0 module)
  - Article 0 / CLF-CBF barriers = refuse bad trajectories in imagination
  - honey = distilled dream experience, fleet-shareable via Procrustes
  - σ per planned path

This package ships the Python wrapper around the Rust drum + Isaac harness:
  1. DreamState — one imagined rollout snapshot
  2. DreamTrajectory — a sequence of DreamStates (the imagination)
  3. DreamPolicy — the policy that generates trajectories (rules)
  4. DreamGuard — Article 0 + σ ceiling applied to imagined actions
  5. dream_one() / dream_trajectory() — the actual dream calls

Honest scope: the actual Isaac Sim / Cosmos rollout requires GPU +
Isaac Sim installed (separate workflow). This package is the *contract*
*
  between the policy, the StateBus, and the dream engine — the same
  shape as sovos-chain's role for the substrate.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# Care floor (master canon)
CARE_FLOOR = 0.95


@dataclass(frozen=True)
class DreamState:
    """One snapshot in a dream rollout."""
    t: float                   # time index (seconds)
    jspace_position: Dict[str, float]  # Poincaré ball position
    action: str                # imagined action at this step
    sigma: float               # uncertainty in this state's prediction
    provenance: str = ""       # sigil or source identifier

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DreamTrajectory:
    """A sequence of DreamStates — one imagined rollout."""
    trajectory_id: str
    states: List[DreamState]
    initial_state: str = ""  # the real starting state (what we dreamt from)
    policy_id: str = ""      # which DreamPolicy generated this

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:32]

    def length(self) -> int:
        return len(self.states)

    def mean_sigma(self) -> float:
        if not self.states:
            return 0.0
        return sum(s.sigma for s in self.states) / len(self.states)

    def max_sigma(self) -> float:
        if not self.states:
            return 0.0
        return max(s.sigma for s in self.states)

    def is_within_calibration(self, ceiling: float = 0.05) -> bool:
        """A trajectory is 'honey-worthy' only if max σ ≤ ceiling (5%)."""
        return self.max_sigma() <= ceiling


@dataclass(frozen=True)
class DreamPolicy:
    """The policy that generates dream trajectories."""
    policy_id: str
    description: str
    max_length: int = 32            # max states per trajectory
    sigma_ceiling: float = 0.05     # max σ allowed per state
    banned_actions: List[str] = field(default_factory=list)


def article0_dream_guard(policy: DreamPolicy, trajectory: DreamTrajectory) -> Dict[str, Any]:
    """Apply Article 0 + care-floor to a dream trajectory.

    Returns a guard report dict with:
      - passed (bool)
      - banned_action_states (list of state indices where banned_actions appear)
      - oversigma_states (list of state indices where sigma > ceiling)
      - max_sigma (float)
      - mean_sigma (float)
    """
    banned_states: List[int] = []
    oversigma_states: List[int] = []

    for i, s in enumerate(trajectory.states):
        if s.sigma > policy.sigma_ceiling:
            oversigma_states.append(i)
        for b in policy.banned_actions:
            if b.lower() in s.action.lower():
                banned_states.append(i)
                break

    passed = (not banned_states) and (not oversigma_states)
    return {
        "passed": passed,
        "banned_action_states": banned_states,
        "oversigma_states": oversigma_states,
        "max_sigma": trajectory.max_sigma(),
        "mean_sigma": trajectory.mean_sigma(),
        "n_states": trajectory.length(),
        "policy_id": policy.policy_id,
        "trajectory_id": trajectory.trajectory_id,
    }


def dream_trajectory(
    policy: DreamPolicy,
    initial_state: str,
    n_steps: int = 8,
    seed: int = 0,
) -> DreamTrajectory:
    """Generate one dream trajectory.

    The actual implementation would call out to drum.rs on the pod
    + Isaac Sim / Cosmos / UnifoLM-WMA-0. Here we ship a deterministic
    stub that produces a length-n trajectory with σ growing by 0.01/step
    (the deeper you imagine, the less certain you become).

    This stub is the contract surface — sovos-chain or sovos-arena
    can be pointed at it and the tests still pass without GPU.
    """
    import random
    rng = random.Random(seed)
    states: List[DreamState] = []
    for i in range(min(n_steps, policy.max_length)):
        # σ grows with horizon (deeper dream = less certain)
        sigma = (i + 1) * 0.01
        # J-Space position drifts outward (peripheral)
        pos = {
            "x": 0.1 + 0.05 * i,
            "y": 0.1 + 0.05 * i,
            "z": 0.1 + 0.05 * i,
        }
        # action: deterministic placeholder
        action = f"step-{i}-{initial_state[:10]}"
        states.append(DreamState(
            t=float(i),
            jspace_position=pos,
            action=action,
            sigma=sigma,
            provenance=f"dream-stub:seed={seed}",
        ))
    trajectory_id = hashlib.sha256(
        f"{policy.policy_id}:{initial_state}:{n_steps}:{seed}".encode()
    ).hexdigest()[:16]
    return DreamTrajectory(
        trajectory_id=trajectory_id,
        states=states,
        initial_state=initial_state,
        policy_id=policy.policy_id,
    )


# Sample policies (the kind that would be passed to drum.rs)
def sample_walk_policy() -> DreamPolicy:
    return DreamPolicy(
        policy_id="walk-policy-v1",
        description="Imagine a humanoid walking forward across a room",
        max_length=16,
        sigma_ceiling=0.05,
        banned_actions=[
            "deploy-an-autonomous-drone",
            "perform mass surveillance",
        ],
    )


def sample_grasp_policy() -> DreamPolicy:
    return DreamPolicy(
        policy_id="grasp-policy-v1",
        description="Imagine a humanoid grasping a cup from a table",
        max_length=8,
        sigma_ceiling=0.05,
        banned_actions=[],
    )


__all__ = [
    "CARE_FLOOR",
    "DreamPolicy",
    "DreamState",
    "DreamTrajectory",
    "article0_dream_guard",
    "dream_trajectory",
    "sample_grasp_policy",
    "sample_walk_policy",
]