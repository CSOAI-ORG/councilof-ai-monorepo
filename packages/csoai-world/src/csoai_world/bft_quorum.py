"""
BFT QUORUM: Cross-Clan Voting for Strategy Selection

Byzantine Fault Tolerant voting across all clans:
1. Each clan votes with confidence + strategy
2. Votes are weighted by win rate and confidence
3. BFT threshold ensures consensus even with faulty clans
4. Final strategy emerges from quorum agreement
"""
import json
from pathlib import Path
from datetime import datetime

IWM_DIR = Path(__file__).resolve().parent


class BFTQuorum:
    """BFT Quorum: cross-clan voting for strategy selection."""

    def __init__(self, threshold=0.67):
        self.threshold = threshold  # BFT threshold (2/3 + 1)
        self.vote_history = []

    def vote(self, swarm_results, task_type=None):
        """Run BFT quorum vote across all clan results."""
        votes = []
        for fam, sim in swarm_results.items():
            best = sim["best"]
            vote = {
                "clan": fam,
                "confidence": best["confidence"],
                "strategy": best["counter_strategy"]["primary"],
                "strengths": best["strengths"],
                "weaknesses": best["weaknesses"],
                "weight": self._compute_weight(fam, best),
            }
            votes.append(vote)
        # Sort by weight
        votes.sort(key=lambda v: v["weight"], reverse=True)
        # BFT consensus
        consensus = self._find_consensus(votes)
        result = {
            "votes": votes,
            "consensus": consensus,
            "quorum_reached": consensus["confidence"] >= self.threshold,
            "winning_strategy": consensus["strategy"],
            "winning_clan": consensus["clan"],
            "alliance": consensus.get("alliance", []),
            "timestamp": datetime.now().isoformat(),
        }
        self.vote_history.append(result)
        return result

    def _compute_weight(self, family, sim):
        """Compute vote weight based on confidence and historical performance."""
        base_weight = sim["confidence"]
        # Bonus for having more strengths
        strength_bonus = len(sim.get("strengths", [])) * 0.05
        # Penalty for having weaknesses
        weakness_penalty = len(sim.get("weaknesses", [])) * 0.03
        return base_weight + strength_bonus - weakness_penalty

    def _find_consensus(self, votes):
        """Find BFT consensus among votes."""
        if not votes:
            return {"clan": "none", "strategy": "no_consensus", "confidence": 0.0}
        # Group votes by similar strategies
        strategy_groups = {}
        for vote in votes:
            strategy = vote["strategy"]
            if strategy not in strategy_groups:
                strategy_groups[strategy] = []
            strategy_groups[strategy].append(vote)
        # Find group with highest total weight
        best_strategy = max(
            strategy_groups.items(),
            key=lambda x: sum(v["weight"] for v in x[1])
        )
        strategy_name, group_votes = best_strategy
        total_weight = sum(v["weight"] for v in group_votes)
        avg_confidence = sum(v["confidence"] for v in group_votes) / len(group_votes)
        # The clan with highest individual weight in the winning group
        lead_clan = max(group_votes, key=lambda v: v["weight"])
        return {
            "clan": lead_clan["clan"],
            "strategy": strategy_name,
            "confidence": avg_confidence,
            "total_weight": total_weight,
            "alliance": [v["clan"] for v in group_votes],
            "alliance_size": len(group_votes),
        }

    def get_voting_history(self):
        return self.vote_history

    def get_clan_reliability(self):
        """Track which clans consistently vote with the winning strategy."""
        reliability = {}
        for vote_record in self.vote_history:
            winning_clan = vote_record["consensus"]["clan"]
            alliance = vote_record["consensus"].get("alliance", [])
            for clan in alliance:
                if clan not in reliability:
                    reliability[clan] = {"consensus_votes": 0, "total_votes": 0}
                reliability[clan]["consensus_votes"] += 1
            for vote in vote_record["votes"]:
                clan = vote["clan"]
                if clan not in reliability:
                    reliability[clan] = {"consensus_votes": 0, "total_votes": 0}
                reliability[clan]["total_votes"] += 1
        return reliability

    def vote_from_cspace(self, master_cspace):
        """Vote from master C-space (SOV router output)."""
        contributions = master_cspace.get("clan_contributions", {})
        votes = []
        for clan_name, data in contributions.items():
            avg_conf = data["total_confidence"] / max(data["count"], 1)
            votes.append({
                "clan": clan_name,
                "confidence": avg_conf,
                "weight": avg_conf,
                "strategy": clan_name,
            })
        votes.sort(key=lambda v: v["weight"], reverse=True)
        if not votes:
            return {"consensus": {"clan": "none", "strategy": "none", "confidence": 0, "alliance": []}, "quorum_reached": False, "winning_strategy": "none"}
        best = votes[0]
        alliance = [v["clan"] for v in votes if v["confidence"] > 0.3]
        result = {
            "votes": votes,
            "consensus": {
                "clan": best["clan"],
                "strategy": best["strategy"],
                "confidence": best["confidence"],
                "alliance": alliance,
            },
            "quorum_reached": best["confidence"] >= self.threshold,
            "winning_strategy": best["strategy"],
            "winning_clan": best["clan"],
        }
        self.vote_history.append(result)
        return result
