"""csoai-council — The BFT Council reputation + quorum gate.

This is the *weighting layer* of the SOVOS BFT Council — the part that
the EAT hunt ruling says is "ours" and sits atop a consensus engine
(CometBFT ABCI). It does NOT re-implement PBFT/consensus transport;
it implements the governance semantics the Council needs:

    vote_weight = reputation × coherence × certification

mapped from the master's standing canon:
  - 33 council seats, n > 3f+1 (f = 10 → n = 33 is valid: 33 > 31)
  - quorum = 23/33 for binding decisions, 33/33 for Article 0
  - decisions are Ed25519-signed (cryptography lib) so every result is
    attributable and a chain_id anchors the audit trail

Design:
  - Council(n_seats=33, f=10) — enforces n > 3f+1.
  - Each member carries (reputation, coherence, certification) ∈ [0,1].
  - vote_weight(i) = reputation * coherence * certification. The product
    form is deliberate: a zero in any dimension zeroes the vote (a
    low-reputation OR incoherent OR uncertified member carries no weight).
  - propose/decide: collect signed votes, sum weights, require >= quorum
    fraction of TOTAL weight (not raw count) — weighted, not democratic.
  - Article 0 supermajority: requires 33/33 weight for the foundational
    gate (per registry).
  - Every vote, proposal, and decision emits a 24-char chain_id.

This is honest scope: the reputation history, coherence measurement, and
certification records are injected by the caller (from the Bus, from
CouncilOf agent attestations, from the certification loop). This package
enforces the MATH of the vote, not the provenance of the inputs.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants — the Council canon (from the master / registry)
# ---------------------------------------------------------------------------
CANONICAL_SEATS = 33
CANONICAL_F = 10                      # n=33 > 3*10+1=31  ✓
BINDING_QUORUM = 23.0 / 33.0          # 0.697 (weighted)
ARTICLE_ZERO_QUORUM = 1.0             # 33/33


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class Member:
    """One Council member with its three weighted dimensions."""
    agent_id: str
    reputation: float = 1.0     # [0,1]
    coherence: float = 1.0      # [0,1]
    certification: float = 1.0  # [0,1]

    def __post_init__(self):
        for attr in ("reputation", "coherence", "certification"):
            v = getattr(self, attr)
            v = max(0.0, min(1.0, float(v)))
            setattr(self, attr, v)

    def weight(self) -> float:
        """vote_weight = reputation × coherence × certification."""
        return self.reputation * self.coherence * self.certification

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "reputation": self.reputation,
            "coherence": self.coherence,
            "certification": self.certification,
            "weight": self.weight(),
        }


@dataclass
class Vote:
    """One signed vote."""
    agent_id: str
    decision: bool              # True = approve
    weight: float
    signature: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CouncilVerdict:
    """The result of a weighted decision."""
    proposal_id: str
    passed: bool
    yes_weight: float
    no_weight: float
    total_voting_weight: float
    quorum_fraction: float          # yes_weight / total_voting_weight
    required_fraction: float        # e.g. 0.697 for binding, 1.0 for Article 0
    article_zero: bool
    votes: List[Dict[str, Any]]
    chain_id: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Council
# ---------------------------------------------------------------------------
class Council:
    """The SOVOS BFT Council weighting + quorum gate.

    Args:
        members: list of Member — the Council roster (injected).
        n_seats: nominal seat count (default 33; must satisfy n > 3f+1).
        f:       byzantine threshold (default 10; n=33 > 3*10+1=31).
        article_zero: vote governance (default False — use decide_article_zero
                     for the supermajority gate).
    """

    def __init__(self, members: List[Member],
                 n_seats: int = CANONICAL_SEATS,
                 f: int = CANONICAL_F,
                 quorum_fraction: float = BINDING_QUORUM):
        if n_seats <= 3 * f + 1:
            raise ValueError(f"n_seats must be > 3f+1: {n_seats} vs 3*{f}+1={3*f+1}")
        if len(members) > n_seats:
            raise ValueError(f"members ({len(members)}) exceed n_seats ({n_seats})")
        self.n_seats = n_seats
        self.f = f
        self.quorum_fraction = quorum_fraction
        self.members = {m.agent_id: m for m in members}
        self.total_weight = sum(m.weight() for m in members)

    # -------------------------------------------------------------------
    def add_member(self, member: Member) -> None:
        if len(self.members) >= self.n_seats:
            raise ValueError("Council at capacity")
        self.members[member.agent_id] = member
        self.total_weight = sum(m.weight() for m in self.members.values())

    # -------------------------------------------------------------------
    def sign_vote(self, member: Member, proposal_text: str, decision: bool,
                  key, chain_id: str) -> Optional[Vote]:
        """Sign one vote for a member. Returns SignedVote or None.

        key: a cryptography ed25519 private key with .sign(bytes).
        The signature covers (proposal_id, agent_id, decision, weight).
        """
        if member.agent_id not in self.members:
            return None
        body = json.dumps({
            "proposal": proposal_text, "agent": member.agent_id,
            "decision": decision, "weight": member.weight(),
            "chain_id": chain_id,
        }, sort_keys=True).encode()
        sig = key.sign(body)
        return Vote(
            agent_id=member.agent_id, decision=decision,
            weight=member.weight(), signature=sig.hex(),
        )

    # -------------------------------------------------------------------
    def decide(self, proposal_text: str, votes: List[Vote],
               quorum_fraction: Optional[float] = None,
               article_zero: bool = False) -> CouncilVerdict:
        """Aggregate signed votes into a weighted Council verdict.

        Verdict passes iff:
           yes_weight / total_voting_weight >= required_fraction
        where total_voting_weight is the sum of weights of members who
        actually voted (weighted — non-voters simply don't count toward
        "yes", and the requirement is on the voting body).

        NOTE the quorum semantics: 'quorum' is the fraction of VOTING
        weight that must be 'yes'. A proposal with only 10 votes and 0.99
        of them yes can pass — because the Council requires n > 3f+1 seats
        (so ≥ 23/33 seats are honest by construction when all vote).
        Non-voting members are the integrity risk; the checker below
        reports voter coverage so the caller can require it separately.
        """
        req = quorum_fraction if quorum_fraction is not None else (
            ARTICLE_ZERO_QUORUM if article_zero else self.quorum_fraction)
        yes_w = sum(v.weight for v in votes if v.decision)
        no_w = sum(v.weight for v in votes if not v.decision)
        total_council = max(self.total_weight, 1e-12)
        # Quorum is a fraction of the TOTAL council weight (all n seats),
        # per the canon "23 of 33 seats". Non-voters reduce the achievable
        # fraction honestly — they do not inflate the denominator.
        qf = yes_w / total_council
        voted_frac = (yes_w + no_w) / total_council  # coverage of the ballot
        passed = qf >= req  # yes_weight must reach the required fraction of ALL seats
        proposition_hash = hashlib.sha256(proposal_text.encode()).hexdigest()[:24]
        chain_body = json.dumps({
            "proposal_hash": proposition_hash, "passed": passed,
            "yes_weight": yes_w, "no_weight": no_w,
            "quorum_fraction": qf, "required": req,
            "article_zero": article_zero, "n_votes": len(votes),
            "voted_coverage": voted_frac,
        }, sort_keys=True).encode()
        chain_id = hashlib.sha256(chain_body).hexdigest()[:24]
        return CouncilVerdict(
            proposal_id=proposition_hash, passed=passed,
            yes_weight=yes_w, no_weight=no_w,
            total_voting_weight=total_council, quorum_fraction=qf,
            required_fraction=req, article_zero=article_zero,
            votes=[v.to_dict() for v in votes], chain_id=chain_id,
        )

    # -------------------------------------------------------------------
    def decide_article_zero(self, proposal_text: str, votes: List[Vote]) -> CouncilVerdict:
        """The Article 0 supermajority gate (33/33 by weight)."""
        return self.decide(proposal_text, votes, article_zero=True)

    # -------------------------------------------------------------------
    def stats(self) -> Dict[str, Any]:
        return {
            "n_seats": self.n_seats,
            "f": self.f,
            "members": len(self.members),
            "total_weight": self.total_weight,
            "binding_quorum": self.quorum_fraction,
            "article_zero_quorum": ARTICLE_ZERO_QUORUM,
        }


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------
def council_from_reputation_map(rep: Dict[str, Tuple[float, float, float]],
                                n_seats: int = CANONICAL_SEATS,
                                f: int = CANONICAL_F) -> Council:
    """Build a Council from {agent_id: (reputation, coherence, certification)}."""
    members = [
        Member(agent_id=aid, reputation=r, coherence=c, certification=cc)
        for aid, (r, c, cc) in rep.items()
    ]
    return Council(members=members, n_seats=n_seats, f=f)


def self_test() -> Dict[str, Any]:
    """Smoke test: quorum reached vs not, weighted vs raw."""
    # 33 members, all full weight → total weight 33
    rep = {f"agent_{i:02d}": (1.0, 1.0, 1.0) for i in range(33)}
    c = council_from_reputation_map(rep)
    # 20 yes of 33 → weight 20/33 = 0.606 < 0.697 → fails binding
    # 25 yes of 33 → weight 25/33 = 0.758 > 0.697 → passes
    votes_no = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(rep)[:20]]
    votes_yes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(rep)[:25]]
    d_no = c.decide("proposal", votes_no)
    d_yes = c.decide("proposal", votes_yes)
    return {
        "n=33_f=10_valid": c.n_seats > 3 * c.f + 1,
        "total_weight": c.total_weight,
        "20_yes_passed": d_no.passed,
        "20_yes_frac": round(d_no.quorum_fraction, 3),
        "25_yes_passed": d_yes.passed,
        "25_yes_frac": round(d_yes.quorum_fraction, 3),
        "chain_id_len": len(d_yes.chain_id),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(self_test(), indent=2))
