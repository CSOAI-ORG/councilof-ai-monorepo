"""
SOV ROUTER: Breaks tasks into subtasks, distributes across all clans

The SOV router is NOT a wrapper — it IS the whole organism.
It:
1. Receives a task from OWM
2. Breaks it into subtasks (task decomposition)
3. Routes each subtask to the best clan(s)
4. Each clan's 4 OWEM brains process in parallel
5. Results aggregate into C-space
6. BFT quorum selects final strategy
7. Honey memory updates across all fluid layers

SOV turns frozen into fluid, evolves clans, creates visual reasoning.
"""
import json, hashlib
from pathlib import Path
from datetime import datetime
from .owem_hive import OWEMHive, CLAN_LAYERS
from .bft_quorum import BFTQuorum
from .g_space import GSpace, FAMILIES, FAMILY_CAPABILITIES

IWM_DIR = Path(__file__).resolve().parent


class SOVRouter:
    """SOV Router: the whole organism, not a wrapper."""

    def __init__(self):
        self.hive = OWEMHive()
        self.bft = BFTQuorum()
        self.g_space = GSpace()
        self.task_log = []
        self.c_space_history = []

    def process(self, task, competitor=None):
        """
        Full SOV processing pipeline:
        1. Decompose task into subtasks
        2. Route subtasks to best clans
        3. Each clan's 4 OWEM brains process
        4. Build C-space from all results
        5. BFT quorum selects final strategy
        """
        # Step 1: Decompose
        subtasks = self._decompose_task(task)
        # Step 2-4: Process each subtask through relevant clans
        all_results = {}
        for subtask in subtasks:
            target_clans = self._route_to_clans(subtask)
            clan_results = self.hive.process_task(subtask["description"], competitor, target_clans)
            all_results[subtask["id"]] = {
                "subtask": subtask,
                "clan_results": clan_results,
            }
        # Step 5: Build master C-space
        master_cspace = self._build_master_cspace(all_results)
        # Step 6: BFT quorum
        quorum_result = self.bft.vote_from_cspace(master_cspace)
        # Step 7: Compile final strategy
        strategy = {
            "task": task,
            "subtasks": len(subtasks),
            "clans_activated": len(set(s["target_clan"] for st in subtasks for s in [st])),
            "master_cspace": master_cspace,
            "quorum": quorum_result,
            "strategy": quorum_result.get("winning_strategy", "default"),
            "confidence": quorum_result.get("consensus", {}).get("confidence", 0),
            "alliance": quorum_result.get("consensus", {}).get("alliance", []),
            "timestamp": datetime.now().isoformat(),
        }
        self.task_log.append(strategy)
        self.c_space_history.append(master_cspace)
        return strategy

    def _decompose_task(self, task):
        """Break a task into subtasks for parallel processing."""
        task_desc = task if isinstance(task, str) else task.get("description", str(task))
        task_type = self._classify_task(task_desc)
        # Generate subtasks based on task type
        subtasks = [
            {"id": "main", "description": task_desc, "type": task_type, "target_clan": task_type},
        ]
        # Add specialized subtasks
        if task_type in ["coding", "reasoning", "math"]:
            subtasks.append({"id": "verify", "description": f"Verify correctness of: {task_desc}", "type": "reasoning", "target_clan": "reasoning"})
        if task_type in ["creative", "writing"]:
            subtasks.append({"id": "style", "description": f"Improve style and clarity of: {task_desc}", "type": "creative", "target_clan": "creative"})
        if task_type in ["compliance", "safety"]:
            subtasks.append({"id": "audit", "description": f"Audit for compliance: {task_desc}", "type": "compliance", "target_clan": "compliance"})
        # Always add knowledge check
        subtasks.append({"id": "knowledge", "description": f"What is known about: {task_desc}", "type": "knowledge", "target_clan": "knowledge"})
        return subtasks

    def _classify_task(self, task_desc):
        """Classify task for routing."""
        desc = task_desc.lower()
        if any(w in desc for w in ["code", "program", "debug", "implement"]):
            return "coding"
        if any(w in desc for w in ["math", "calculat", "equation", "proof"]):
            return "math"
        if any(w in desc for w in ["translat", "language", "multilingual"]):
            return "multilingual"
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
        return "reasoning"

    def _route_to_clans(self, subtask):
        """Route a subtask to the best clan(s)."""
        target = subtask.get("target_clan", "reasoning")
        if target in CLAN_LAYERS:
            return [target]
        # Default: route to reasoning + knowledge
        return ["reasoning", "knowledge"]

    def _build_master_cspace(self, all_results):
        """Build master C-space from all subtask results."""
        master = {
            "subtasks": {},
            "clan_contributions": {},
            "best_strategy": None,
            "total_confidence": 0,
            "count": 0,
        }
        for subtask_id, result in all_results.items():
            subtask_cspace = {}
            for clan_name, clan_result in result["clan_results"].items():
                subtask_cspace[clan_name] = {
                    "confidence": clan_result["confidence"],
                    "best_family": clan_result["best_family"],
                    "specialist": clan_result["specialist"],
                }
                # Track clan contributions
                if clan_name not in master["clan_contributions"]:
                    master["clan_contributions"][clan_name] = {"total_confidence": 0, "count": 0}
                master["clan_contributions"][clan_name]["total_confidence"] += clan_result["confidence"]
                master["clan_contributions"][clan_name]["count"] += 1
                master["total_confidence"] += clan_result["confidence"]
                master["count"] += 1
            master["subtasks"][subtask_id] = subtask_cspace
        # Find best strategy
        if master["clan_contributions"]:
            best_clan = max(master["clan_contributions"].items(), key=lambda x: x[1]["total_confidence"] / max(x[1]["count"], 1))
            master["best_strategy"] = best_clan[0]
        master["avg_confidence"] = master["total_confidence"] / max(master["count"], 1)
        return master

    def learn(self, outcome):
        """Feed outcome back into all activated clans."""
        clan = outcome.get("clan", "reasoning")
        family = outcome.get("family", "deepseek")
        self.hive.learn_from_outcome(clan, family, outcome)

    def run_pdca(self, task):
        """PDCA interface for OWM compatibility."""
        result = self.process(task)
        return {
            "cycle": 1,
            "strategy": result["strategy"],
            "confidence": result["confidence"],
            "alliance": result["alliance"],
            "plan": {"selected_clans": list(self.hive.clans.keys()), "task_type": self._classify_task(task.get("description", str(task)) if isinstance(task, dict) else str(task))},
            "check": {"quorum": result["quorum"]},
            "act": {"alliance_updated": result["alliance"], "gnn_updated": True, "honey_memory_updated": True, "recommendations": []},
        }

    def receive_outcome(self, task, won, details=None):
        """Receive outcome for OWM compatibility."""
        self.learn({"task": task.get("description", str(task)), "won": won, "competitor": task.get("competitor", {}).get("name", "unknown")})

    def get_status(self):
        return {
            "hive_topology": self.hive.get_topology(),
            "tasks_processed": len(self.task_log),
            "stigmergy": self.hive.stigmergy.get_signal_summary(),
        }
