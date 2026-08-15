"""
IWM: Inner World Model — Main Orchestrator with PDCA

The IWM is the top-level orchestrator that:
1. Manages G-space (knowledge graph + GNN)
2. Manages the clan engine (family swarms)
3. Manages the BFT quorum (voting)
4. Runs PDCA cycles for continuous improvement
5. Coordinates frozen → fluid transitions

PDCA Cycle:
  PLAN  → Analyze task, select clans, plan approach
  DO    → Execute simulations across all selected clans
  CHECK → BFT quorum evaluates results, picks best strategy
  ACT   → Feed outcomes to honey memory, update GNN for next cycle

Each PDCA cycle improves the next. Multiple cycles = compounding advantage.
"""
import json, time
from pathlib import Path
from datetime import datetime

from .g_space import GSpace, FAMILIES
from .j_space import JSpace
from .clan_engine import ClanEngine
from .bft_quorum import BFTQuorum

IWM_DIR = Path(__file__).resolve().parent
IWM_STATE = IWM_DIR / "iwm_state.json"


class IWM:
    """Inner World Model: Sovereign Swarm Intelligence with PDCA."""

    def __init__(self, g_space=None):
        self.g_space = g_space or GSpace()
        self.clan_engine = ClanEngine(self.g_space)
        self.bft_quorum = BFTQuorum()
        self.state = self._load_state()
        self.pdca_log = []
        self.c_space_log = []

    def _load_state(self):
        state = {
            "initialized": datetime.now().isoformat(),
            "total_pdca_cycles": 0,
            "total_tasks": 0,
            "total_wins": 0,
            "total_losses": 0,
            "fluid_clans": [],
            "frozen_clans": list(FAMILIES),
        }
        if IWM_STATE.exists():
            try:
                loaded = json.loads(IWM_STATE.read_text())
                state.update(loaded)
            except Exception:
                pass
        return state

    def save_state(self):
        IWM_STATE.write_text(json.dumps(self.state, indent=2))

    # ─── PDCA CYCLE ───────────────────────────────────────────

    def run_pdca(self, task, cycles=1):
        """
        Run PDCA cycle(s) on a task.
        
        More cycles = better strategy through iterative refinement.
        
        Args:
            task: dict with description, type, competitor, etc.
            cycles: number of PDCA iterations (default 1, more = better)
        
        Returns:
            Final optimized strategy after all cycles
        """
        task_desc = task.get("description", str(task))
        competitor = task.get("competitor", {})
        competitor_name = competitor.get("name", "unknown") if isinstance(competitor, dict) else str(competitor)
        
        best_result = None
        for cycle_num in range(1, cycles + 1):
            # ── PLAN ──
            plan = self._plan(task_desc, competitor, cycle_num, best_result)
            # ── DO ──
            swarm_results = self._do(task_desc, competitor_name, plan)
            # ── CHECK ──
            check_result = self._check(swarm_results, plan)
            # ── ACT ──
            act_result = self._act(task_desc, competitor_name, check_result, cycle_num)
            best_result = {
                "cycle": cycle_num,
                "plan": plan,
                "check": check_result,
                "act": act_result,
                "strategy": check_result["quorum"]["winning_strategy"],
                "confidence": check_result["quorum"]["consensus"]["confidence"],
                "alliance": check_result["quorum"]["consensus"].get("alliance", []),
                "recommendations": act_result.get("recommendations", []),
            }
            self.state["total_pdca_cycles"] += 1
            self.pdca_log.append(best_result)
        self.state["total_tasks"] += 1
        self.save_state()
        return best_result

    def _plan(self, task_desc, competitor, cycle_num, prior_result):
        """PDCA PLAN: Analyze task, select clans, plan approach."""
        # Route to best clans based on task
        ranked = self.g_space.route(task_desc, competitor.get("name") if isinstance(competitor, dict) else None)
        # Select top clans (more on first cycle, fewer on refinement)
        top_n = max(5, 19 - (cycle_num - 1) * 3)
        selected = [fam for fam, _ in ranked[:top_n]]
        # Identify task type
        task_type = self._classify_task(task_desc)
        # Plan adjustments from prior cycle
        adjustments = []
        if prior_result:
            if prior_result["confidence"] < 0.7:
                adjustments.append("expand_clan_selection")
                top_n = min(19, top_n + 3)
                selected = [fam for fam, _ in ranked[:top_n]]
            if prior_result.get("act", {}).get("new_patterns_found"):
                adjustments.append("apply_new_patterns")
        return {
            "selected_clans": selected,
            "top_n": top_n,
            "task_type": task_type,
            "cycle_num": cycle_num,
            "adjustments": adjustments,
            "competitor_analysis": competitor,
        }

    def _do(self, task_desc, competitor_name, plan):
        """PDCA DO: Execute simulations across all selected clans."""
        results = {}
        for fam in plan["selected_clans"]:
            frozen_sim = self.clan_engine.clans[fam]["frozen"].simulate_competitor(competitor_name, task_desc)
            fluid_sim = self.clan_engine.clans[fam]["fluid"].simulate_competitor(competitor_name, task_desc)
            results[fam] = {
                "frozen": frozen_sim,
                "fluid": fluid_sim,
                "best": fluid_sim if fluid_sim["confidence"] > frozen_sim["confidence"] else frozen_sim,
            }
        return results

    def _check(self, swarm_results, plan):
        """PDCA CHECK: BFT quorum evaluates and picks best strategy."""
        quorum_result = self.bft_quorum.vote(swarm_results, task_type=plan["task_type"])
        c_space = self._build_c_space(swarm_results, quorum_result)
        return {
            "quorum": quorum_result,
            "c_space": c_space,
            "clans_evaluated": len(swarm_results),
            "quorum_reached": quorum_result["quorum_reached"],
        }

    def _act(self, task_desc, competitor_name, check_result, cycle_num):
        """PDCA ACT: Feed outcomes to honey memory, update GNN."""
        quorum = check_result["quorum"]
        winning_clan = quorum["winning_clan"]
        alliance = quorum["consensus"].get("alliance", [])
        # Update honey memory for all alliance members
        for fam in alliance:
            self.clan_engine.clans[fam]["fluid"].learn_from_outcome(
                task=task_desc,
                won=True,  # Assume strategy is optimal for now
                competitor=competitor_name,
                strategy_used={"primary": quorum["winning_strategy"]},
            )
        # Update G-space routing bias
        for fam in alliance:
            self.g_space.record_outcome(fam, competitor_name, True, task_desc)
        # Generate recommendations for next cycle
        recommendations = []
        confidence = quorum["consensus"]["confidence"]
        if confidence < 0.6:
            recommendations.append("Low confidence — consider expanding clan selection")
        if len(alliance) < 3:
            recommendations.append("Small alliance — consider recruiting more clans")
        if cycle_num > 1:
            recommendations.append(f"Cycle {cycle_num} refinement applied")
        # Check for new patterns in honey memory
        new_patterns = False
        for fam in alliance:
            honey = self.clan_engine.clans[fam]["fluid"].honey_memory
            if len(honey.get("win_patterns", {})) > 3:
                new_patterns = True
        return {
            "alliance_updated": alliance,
            "gnn_updated": True,
            "honey_memory_updated": True,
            "recommendations": recommendations,
            "new_patterns_found": new_patterns,
            "confidence_after": confidence,
        }

    def _classify_task(self, task_desc):
        """Classify task type for routing."""
        desc = task_desc.lower()
        if any(w in desc for w in ["code", "program", "debug", "implement"]):
            return "coding"
        if any(w in desc for w in ["math", "calculat", "equation", "proof"]):
            return "math"
        if any(w in desc for w in ["translat", "language", "multilingual"]):
            return "translation"
        if any(w in desc for w in ["image", "vision", "visual", "photo"]):
            return "vision"
        if any(w in desc for w in ["write", "story", "creative", "poem"]):
            return "creative"
        if any(w in desc for w in ["analyz", "reason", "logic", "think"]):
            return "reasoning"
        if any(w in desc for w in ["comply", "regulat", "audit", "legal"]):
            return "compliance"
        if any(w in desc for w in ["deploy", "infra", "server", "scale"]):
            return "infrastructure"
        return "general"

    # ─── OUTCOME TRACKING ─────────────────────────────────────

    def receive_outcome(self, task, won, details=None):
        """Receive real-world outcome and update all systems."""
        task_desc = task.get("description", str(task))
        competitor = task.get("competitor", {})
        comp_name = competitor.get("name", "unknown") if isinstance(competitor, dict) else str(competitor)
        # Update all clans
        for fam in FAMILIES:
            self.clan_engine.clans[fam]["fluid"].learn_from_outcome(
                task=task_desc, won=won, competitor=comp_name,
                strategy_used={"primary": "real_outcome"},
            )
            self.g_space.record_outcome(fam, comp_name, won, task_desc)
        if won:
            self.state["total_wins"] += 1
        else:
            self.state["total_losses"] += 1
        self.save_state()

    # ─── C-SPACE ──────────────────────────────────────────────

    def _build_c_space(self, swarm_results, quorum_result):
        """Build C-space: composite of all clan J-spaces."""
        c_space = {
            "families": {},
            "alliance": quorum_result["consensus"].get("alliance", []),
            "winning_clan": quorum_result["winning_clan"],
        }
        for fam, sim in swarm_results.items():
            c_space["families"][fam] = {
                "frozen_confidence": sim["frozen"]["confidence"],
                "fluid_confidence": sim["fluid"]["confidence"],
                "best_mode": "fluid" if sim["fluid"]["confidence"] > sim["frozen"]["confidence"] else "frozen",
                "strengths": sim["best"]["strengths"],
                "strategy": sim["best"]["counter_strategy"]["primary"],
            }
        self.c_space_log.append({
            "c_space": c_space,
            "timestamp": datetime.now().isoformat(),
        })
        return c_space

    # ─── STATUS ───────────────────────────────────────────────

    def get_status(self):
        wins = self.state["total_wins"]
        losses = self.state["total_losses"]
        total = wins + losses
        return {
            "state": self.state,
            "topology": self.g_space.get_topology(),
            "clan_count": len(FAMILIES),
            "pdca_cycles_completed": self.state["total_pdca_cycles"],
            "win_rate": wins / max(total, 1),
            "total_outcomes": total,
        }

    def get_topology(self):
        return {
            "sov_space": {
                "g_space": self.g_space.get_topology(),
                "clans": {fam: {"frozen": True, "fluid": True} for fam in FAMILIES},
                "bft_quorum": {"threshold": self.bft_quorum.threshold},
                "pdca_cycles": self.state["total_pdca_cycles"],
            },
        }
