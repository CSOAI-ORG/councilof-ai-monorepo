"""
CLAN ENGINE: Spawns Family Swarms

The clan engine manages:
1. Spawning J-spaces for each family
2. Running parallel simulations across all families
3. Collecting results and feeding to G-space
4. Managing frozen → fluid transitions
"""
import json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .j_space import JSpace
from .g_space import GSpace, FAMILIES

ROOT = Path(__file__).resolve().parent.parent
IWM_DIR = ROOT / "iwms"


class ClanEngine:
    """Clan Engine: spawns and manages family swarms."""

    def __init__(self, g_space=None):
        self.g_space = g_space or GSpace()
        self.clans = {}
        self._init_clans()

    def _init_clans(self):
        """Initialize all family clans with both frozen and fluid J-spaces."""
        for fam in FAMILIES:
            self.clans[fam] = {
                "frozen": JSpace(fam, mode="frozen"),
                "fluid": JSpace(fam, mode="fluid"),
            }

    def spawn_swarm(self, task, competitor=None, mode="auto"):
        """Spawn a swarm of all clans to simulate against a task/competitor."""
        results = {}
        for fam in FAMILIES:
            frozen_sim = self.clans[fam]["frozen"].simulate_competitor(
                competitor or "unknown", task
            )
            fluid_sim = self.clans[fam]["fluid"].simulate_competitor(
                competitor or "unknown", task
            )
            results[fam] = {
                "frozen": frozen_sim,
                "fluid": fluid_sim,
                "best": fluid_sim if fluid_sim["confidence"] > frozen_sim["confidence"] else frozen_sim,
            }
        return results

    def spawn_targeted(self, task, top_n=5, competitor=None):
        """Spawn only the top N clans (routed by G-space)."""
        ranked = self.g_space.route(task, competitor)
        top_families = [fam for fam, _ in ranked[:top_n]]
        results = {}
        for fam in top_families:
            frozen_sim = self.clans[fam]["frozen"].simulate_competitor(
                competitor or "unknown", task
            )
            fluid_sim = self.clans[fam]["fluid"].simulate_competitor(
                competitor or "unknown", task
            )
            results[fam] = {
                "frozen": frozen_sim,
                "fluid": fluid_sim,
                "best": fluid_sim if fluid_sim["confidence"] > frozen_sim["confidence"] else frozen_sim,
            }
        return results

    def learn_all(self, task, won, competitor, strategy_used):
        """Propagate learning to all clans."""
        for fam in FAMILIES:
            self.clans[fam]["fluid"].learn_from_outcome(task, won, competitor, strategy_used)
            self.g_space.record_outcome(fam, competitor, won, task)

    def get_clan_status(self):
        """Get status of all clans."""
        status = {}
        for fam in FAMILIES:
            status[fam] = {
                "frozen": self.clans[fam]["frozen"].get_status(),
                "fluid": self.clans[fam]["fluid"].get_status(),
            }
        return status

    def get_swarm_summary(self, results):
        """Summarize swarm simulation results."""
        summary = {
            "total_clans": len(results),
            "avg_confidence": 0.0,
            "best_clan": None,
            "best_confidence": 0.0,
            "clan_details": {},
        }
        for fam, sim in results.items():
            conf = sim["best"]["confidence"]
            summary["avg_confidence"] += conf
            if conf > summary["best_confidence"]:
                summary["best_confidence"] = conf
                summary["best_clan"] = fam
            summary["clan_details"][fam] = {
                "confidence": conf,
                "strengths": sim["best"]["strengths"],
                "weaknesses": sim["best"]["weaknesses"],
                "strategy": sim["best"]["counter_strategy"]["primary"],
            }
        summary["avg_confidence"] /= len(results) if results else 1
        return summary
