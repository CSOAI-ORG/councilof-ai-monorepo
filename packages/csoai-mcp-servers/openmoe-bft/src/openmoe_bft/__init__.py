"""openmoe-bft — SCAFFOLD (v0.1.0).

3-voter BFT consensus. Production version needs reputation, stake, persistence.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Vote:
    voter_id: str
    decision: str  # "approve" | "reject" | "abstain"
    weight: float = 1.0
    reason: Optional[str] = None


@dataclass
class ConsensusResult:
    consensus: str           # "approve" | "reject" | "no_consensus"
    approving_weight: float
    rejecting_weight: float
    abstaining_weight: float
    total_weight: float
    byzantine_voters: List[str]
    vote_breakdown: Dict[str, float]  # decision → weight


def consensus(votes: List[Vote], quorum_fraction: float = 2/3) -> ConsensusResult:
    """Compute BFT consensus over a list of votes.

    A decision is "the consensus" iff its total weight ≥ quorum_fraction × total_weight.

    Voters who disagreed with the consensus are flagged as byzantine.
    """
    if not votes:
        return ConsensusResult(
            consensus="no_consensus", approving_weight=0.0, rejecting_weight=0.0,
            abstaining_weight=0.0, total_weight=0.0, byzantine_voters=[],
            vote_breakdown={},
        )
    total_weight = sum(v.weight for v in votes)
    decision_weights: Dict[str, float] = {}
    for v in votes:
        decision_weights[v.decision] = decision_weights.get(v.decision, 0.0) + v.weight
    # Find the decision with highest weight
    best_decision = max(decision_weights.items(), key=lambda kv: kv[1])
    consensus_decision = best_decision[0]
    best_weight = best_decision[1]
    # Check quorum
    if best_weight >= quorum_fraction * total_weight:
        result_decision = consensus_decision
    else:
        result_decision = "no_consensus"
    # Byzatine voters = those who voted differently from the consensus
    byzantine = []
    if result_decision != "no_consensus":
        byzantine = [v.voter_id for v in votes if v.decision != result_decision]
    return ConsensusResult(
        consensus=result_decision,
        approving_weight=decision_weights.get("approve", 0.0),
        rejecting_weight=decision_weights.get("reject", 0.0),
        abstaining_weight=decision_weights.get("abstain", 0.0),
        total_weight=total_weight,
        byzantine_voters=byzantine,
        vote_breakdown=decision_weights,
    )


def required_quorum(n_voters: int) -> int:
    """Return the minimum number of voters needed for quorum (= 2n/3 + 1)."""
    return math.ceil(2 * n_voters / 3) + 1


def main() -> None:
    """Demo consensus."""
    # 5 voters, 3 approve, 2 reject — consensus = approve (3/5 = 0.6, but 0.6 < 0.667!)
    votes = [
        Vote("alice", "approve", 1.0),
        Vote("bob", "approve", 1.0),
        Vote("carol", "approve", 1.0),
        Vote("dave", "reject", 1.0),
        Vote("eve", "reject", 1.0),
    ]
    r = consensus(votes)
    print(f"  3-vs-2 unanimous-vote: {r.consensus} (weight: {r.approving_weight}/{r.total_weight})")
    print(f"    byzantine: {r.byzantine_voters}")
    # 5 voters, 4 approve, 1 reject — consensus = approve (4/5 = 0.8 >= 0.667)
    votes2 = [
        Vote("alice", "approve", 1.0),
        Vote("bob", "approve", 1.0),
        Vote("carol", "approve", 1.0),
        Vote("dave", "approve", 1.0),
        Vote("eve", "reject", 1.0),
    ]
    r2 = consensus(votes2)
    print(f"  4-vs-1: {r2.consensus} (byzantine: {r2.byzantine_voters})")


if __name__ == "__main__":
    main()


__all__ = ["Vote", "ConsensusResult", "consensus", "required_quorum", "main"]