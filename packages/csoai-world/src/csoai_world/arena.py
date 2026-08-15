"""
ARENA: Kaggle/Competition Entry Point

The arena is where SOV enters competitions against other AI models:
1. Receives competition/task description
2. Spawns clan swarm
3. Runs BFT quorum for strategy selection
4. Executes strategy
5. Records outcome for learning
"""
import json
from pathlib import Path
from datetime import datetime

from .g_space import GSpace
from .clan_engine import ClanEngine
from .bft_quorum import BFTQuorum

IWM_DIR = Path(__file__).resolve().parent


class Arena:
    """Arena: competitive entry point for Kaggle/competitions."""

    def __init__(self, g_space=None):
        self.g_space = g_space or GSpace()
        self.clan_engine = ClanEngine(self.g_space)
        self.bft_quorum = BFTQuorum()
        self.match_history = []

    def enter(self, task_description, competitor=None, mode="full"):
        """
        Enter an arena with a task.
        
        Args:
            task_description: What the task/competition requires
            competitor: Description of the competitor model (optional)
            mode: "full" (all 19 clans), "targeted" (top 5), "fast" (top 3)
        
        Returns:
            Strategy to execute against the competitor
        """
        # Step 1: Route to best clans
        if mode == "full":
            swarm_results = self.clan_engine.spawn_swarm(task_description, competitor)
        elif mode == "targeted":
            swarm_results = self.clan_engine.spawn_targeted(task_description, top_n=5, competitor=competitor)
        else:  # fast
            swarm_results = self.clan_engine.spawn_targeted(task_description, top_n=3, competitor=competitor)
        # Step 2: BFT quorum vote
        quorum_result = self.bft_quorum.vote(swarm_results, task_type=task_description)
        # Step 3: Compile strategy
        strategy = {
            "task": task_description,
            "competitor": competitor,
            "mode": mode,
            "clans_spawned": len(swarm_results),
            "quorum": quorum_result,
            "winning_clan": quorum_result["winning_clan"],
            "winning_strategy": quorum_result["winning_strategy"],
            "alliance": quorum_result["alliance"],
            "confidence": quorum_result["consensus"]["confidence"],
            "swarm_summary": self.clan_engine.get_swarm_summary(swarm_results),
            "timestamp": datetime.now().isoformat(),
        }
        self.match_history.append(strategy)
        return strategy

    def record_outcome(self, strategy, won):
        """Record the outcome of an arena match for learning."""
        self.clan_engine.learn_all(
            task=strategy["task"],
            won=won,
            competitor=strategy.get("competitor", "unknown"),
            strategy_used={"primary": strategy["winning_strategy"]},
        )

    def get_match_history(self):
        return self.match_history

    def get_leaderboard(self):
        """Get clan leaderboard based on arena performance."""
        reliability = self.bft_quorum.get_clan_reliability()
        win_rates = self.g_space.win_memory.get("family_win_rates", {})
        leaderboard = []
        for fam in set(list(reliability.keys()) + list(win_rates.keys())):
            rel = reliability.get(fam, {"consensus_votes": 0, "total_votes": 0})
            wr = win_rates.get(fam, {"wins": 0, "losses": 0})
            total_matches = wr["wins"] + wr["losses"]
            leaderboard.append({
                "family": fam,
                "consensus_rate": rel["consensus_votes"] / rel["total_votes"] if rel["total_votes"] > 0 else 0,
                "win_rate": wr["wins"] / total_matches if total_matches > 0 else 0,
                "total_matches": total_matches,
                "total_votes": rel["total_votes"],
            })
        leaderboard.sort(key=lambda x: x["win_rate"], reverse=True)
        return leaderboard
