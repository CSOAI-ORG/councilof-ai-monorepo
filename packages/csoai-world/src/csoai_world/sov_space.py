"""
SOV-SPACE: The Complete Fractal Hive Architecture

SOV-Space is the top-level container:
- 12 OWEM Hives (one per domain cluster)
- Each hive has 12 Clan Layers (144 total)
- Each clan has 12 Families (1,728 total)
- Each family has 4 Models (6,912 total)

    SOV-SPACE
    ├── HIVE 1: REASONING CLUSTER
    │   ├── Clan: deepseek [12 families]
    │   ├── Clan: qwen [12 families]
    │   ├── Clan: llama [12 families]
    │   ...
    │   └── Clan: nemotron [12 families]
    ├── HIVE 2: CODING CLUSTER
    │   ├── Clan: code [12 families]
    │   ...
    ├── HIVE 3: VISION CLUSTER
    ...
    └── HIVE 12: INFRA CLUSTER

Each family is an OWEM Sandwich Brain:
    OWM-Frozen (perception, stable)
    OWM-Fluid (perception, adapting)
    IWM-Frozen (reasoning, stable)
    IWM-Fluid (reasoning, evolving)

Connected by:
    Spine Drum (heartbeat synchronizer)
    Stigmergy (Pheromone + Waggle + Pollen)
    Constitutional AI (safety layer)
    RAG Pipeline (knowledge retrieval)
    Speculative Decoding (speed)
"""
import json, time, hashlib, threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from .owem_brain import OWEMBrain
from .stigmergy import DistributedStigmergy
from .constitutional_ai import ConstitutionalAI
from .rag_pipeline import RAGPipeline
from .arena_integration import ArenaIntegration
from .unified_gnn import UnifiedGNN

IWM_DIR = Path(__file__).resolve().parent

# 12 Hive Clusters — each hive specializes in a domain
HIVE_CLUSTERS = {
    "reasoning": {
        "clans": ["deepseek", "qwen", "llama", "nemotron", "gpt-oss", "MiniMax", "arch", "research", "phi", "mistral", "gemma", "code"],
        "specialist": "deepseek",
    },
    "coding": {
        "clans": ["code", "deepseek", "qwen", "mistral", "gpt-oss", "nemotron", "phi", "llama", "infra", "MiniMax", "arch", "distribution"],
        "specialist": "code",
    },
    "vision": {
        "clans": ["vision", "qwen-vision", "gemma", "MiniMax", "llama", "qwen", "mistral", "nemotron", "deepseek", "phi", "gpt-oss", "code"],
        "specialist": "vision",
    },
    "multilingual": {
        "clans": ["qwen", "mistral", "llama", "MiniMax", "deepseek", "gemma", "nemotron", "gpt-oss", "phi", "code", "vision", "embedding"],
        "specialist": "qwen",
    },
    "math": {
        "clans": ["deepseek", "phi", "nemotron", "qwen", "mistral", "llama", "gpt-oss", "MiniMax", "code", "arch", "research", "gemma"],
        "specialist": "deepseek",
    },
    "safety": {
        "clans": ["gemma", "llama", "core", "compliance", "qwen", "mistral", "deepseek", "nemotron", "gpt-oss", "MiniMax", "phi", "research"],
        "specialist": "gemma",
    },
    "creative": {
        "clans": ["llama", "qwen", "mistral", "gpt-oss", "deepseek", "MiniMax", "gemma", "nemotron", "phi", "code", "vision", "arch"],
        "specialist": "llama",
    },
    "knowledge": {
        "clans": ["research", "core", "arch", "deepseek", "qwen", "llama", "nemotron", "gpt-oss", "mistral", "gemma", "phi", "compliance"],
        "specialist": "research",
    },
    "tool_use": {
        "clans": ["code", "qwen", "mistral", "infra", "deepseek", "nemotron", "gpt-oss", "llama", "MiniMax", "phi", "distribution", "arch"],
        "specialist": "code",
    },
    "edge": {
        "clans": ["phi", "gemma", "embedding", "distribution", "mistral", "llama", "qwen", "nemotron", "MiniMax", "gpt-oss", "code", "infra"],
        "specialist": "phi",
    },
    "compliance": {
        "clans": ["compliance", "core", "research", "arch", "gemma", "llama", "qwen", "deepseek", "nemotron", "mistral", "gpt-oss", "phi"],
        "specialist": "compliance",
    },
    "infrastructure": {
        "clans": ["infra", "distribution", "code", "gpt-oss", "mistral", "qwen", "deepseek", "nemotron", "llama", "MiniMax", "phi", "gemma"],
        "specialist": "infra",
    },
}

# 12 Families available to each clan
ALL_FAMILIES = [
    "qwen", "deepseek", "llama", "mistral", "gemma", "phi", "gpt-oss",
    "code", "vision", "embedding", "qwen-vision", "MiniMax", "nemotron",
    "core", "research", "arch", "compliance", "distribution", "infra"
]


class SOVSpace:
    """SOV-Space: The complete fractal hive architecture."""

    def __init__(self, lazy=True):
        self.hives = {}
        self.stigmergy = DistributedStigmergy()
        self.constitutional_ai = ConstitutionalAI()
        self.rag_pipeline = RAGPipeline()
        self.arena = ArenaIntegration()
        self.gnn = UnifiedGNN()
        self.task_log = []
        self.lazy = lazy
        self._brain_cache = {}
        if not lazy:
            self._build_hives()
        else:
            self._build_hive_skeleton()
        # Init distributed stigmergy for all hive names
        self.stigmergy.init_hives(list(HIVE_CLUSTERS.keys()))

    def _build_hive_skeleton(self):
        """Build hive structure without creating all brains (lazy mode)."""
        for hive_id, (hive_name, config) in enumerate(HIVE_CLUSTERS.items()):
            clans = {}
            for clan_id, clan_name in enumerate(config["clans"]):
                families = [clan_name] + [f for f in ALL_FAMILIES if f != clan_name][:11]
                clans[clan_name] = {
                    "id": clan_id,
                    "name": clan_name,
                    "specialist": clan_name,
                    "families": families,
                    "brains": {},  # Lazy — created on demand
                    "c_space": {},
                }
            self.hives[hive_name] = {
                "id": hive_id,
                "name": hive_name,
                "specialist": config["specialist"],
                "clans": clans,
            }

    def _get_brain(self, hive_name, clan_name, family):
        """Get or create a brain (lazy loading)."""
        key = f"{hive_name}:{clan_name}:{family}"
        if key not in self._brain_cache:
            self._brain_cache[key] = OWEMBrain(family=family, clan_id=self.hives[hive_name]["clans"][clan_name]["id"])
        return self._brain_cache[key]

    def _build_hives(self):
        """Build all 12 hive clusters."""
        for hive_id, (hive_name, config) in enumerate(HIVE_CLUSTERS.items()):
            clans = {}
            for clan_id, clan_name in enumerate(config["clans"]):
                # Each clan has 12 families (use ALL_FAMILIES, but specialist gets priority)
                families = [clan_name] + [f for f in ALL_FAMILIES if f != clan_name][:11]
                brains = {}
                for fam in families:
                    brains[fam] = OWEMBrain(family=fam, clan_id=clan_id)
                clans[clan_name] = {
                    "id": clan_id,
                    "name": clan_name,
                    "specialist": clan_name,
                    "families": families,
                    "brains": brains,
                    "c_space": {},
                }
            self.hives[hive_name] = {
                "id": hive_id,
                "name": hive_name,
                "specialist": config["specialist"],
                "clans": clans,
            }

    def process(self, task, competitor=None):
        """
        Full SOV-Space processing with GNN dreaming:
        1. Dream competition before entering
        2. Constitutional AI safety check
        3. RAG pipeline for knowledge retrieval
        4. Route to best hive(s) using dream insights
        5. Each hive's clans process in parallel
        6. Each clan's families process (frozen + fluid)
        7. Stigmergy propagates signals (distributed)
        8. Gossip round: peer-to-peer propagation
        9. Aggregate into master C-space
        10. Update GNN with results
        """
        desc = task if isinstance(task, str) else task.get("description", str(task))

        # Step 1: Dream competition before entering
        dream = self.gnn.dream_before_competing("arena", desc, competitor)

        # Step 2: Safety check
        safety_result = self.constitutional_ai.check(task)
        if not safety_result["safe"]:
            return {"error": "Constitutional AI blocked task", "reason": safety_result["reason"]}

        # Step 3: RAG knowledge retrieval
        rag_context = self.rag_pipeline.retrieve(task)

        # Step 4: Route to best hive(s) using dream insights
        target_hives = self._route_to_hives(task)

        # Step 5-6: Process through target hives
        all_results = {}
        for hive_name in target_hives:
            hive = self.hives[hive_name]
            hive_results = self._process_hive(hive, task, competitor, rag_context)
            all_results[hive_name] = hive_results

        # Step 7-8: Distributed stigmergy propagation
        for hive_name, hive_results in all_results.items():
            self.stigmergy.propagate(hive_name, hive_results)
        self.stigmergy.gossip_round()

        # Step 9: Aggregate into master C-space
        master_cspace = self._aggregate_cspace(all_results)

        # Step 10: Update GNN with results
        self.gnn.inner.update_pdca({
            "task": desc[:100],
            "confidence": master_cspace.get("avg_confidence", 0),
            "hives": len(target_hives),
        })
        self.gnn.bridge_update("inner", "outer", {"confidence": master_cspace.get("avg_confidence", 0)})

        # Compile strategy
        strategy = {
            "task": task,
            "dream": dream,
            "hives_activated": len(target_hives),
            "total_clans": sum(len(self.hives[h]["clans"]) for h in target_hives),
            "total_brains": sum(len(self.hives[h]["clans"]) * 12 for h in target_hives),
            "total_models": sum(len(self.hives[h]["clans"]) * 12 * 4 for h in target_hives),
            "master_cspace": master_cspace,
            "rag_context": rag_context[:200] if rag_context else None,
            "safety": safety_result,
            "gnn_status": self.gnn.get_status(),
            "timestamp": datetime.now().isoformat(),
        }
        self.task_log.append(strategy)
        return strategy

    def _route_to_hives(self, task):
        """Route task to best hive(s)."""
        desc = task if isinstance(task, str) else task.get("description", str(task))
        desc = desc.lower()
        hives = []
        if any(w in desc for w in ["reason", "logic", "think", "analyz"]):
            hives.append("reasoning")
        if any(w in desc for w in ["code", "program", "debug", "implement"]):
            hives.append("coding")
        if any(w in desc for w in ["image", "vision", "visual", "photo"]):
            hives.append("vision")
        if any(w in desc for w in ["translat", "language", "multilingual"]):
            hives.append("multilingual")
        if any(w in desc for w in ["math", "calculat", "equation"]):
            hives.append("math")
        if any(w in desc for w in ["safe", "harm", "danger"]):
            hives.append("safety")
        if any(w in desc for w in ["write", "story", "creative", "poem"]):
            hives.append("creative")
        if any(w in desc for w in ["fact", "knowledge", "information"]):
            hives.append("knowledge")
        if any(w in desc for w in ["tool", "function", "api", "call"]):
            hives.append("tool_use")
        if any(w in desc for w in ["edge", "mobile", "embed", "light"]):
            hives.append("edge")
        if any(w in desc for w in ["comply", "regulat", "audit", "legal"]):
            hives.append("compliance")
        if any(w in desc for w in ["deploy", "infra", "server", "scale"]):
            hives.append("infrastructure")
        if not hives:
            hives = ["reasoning", "knowledge"]  # Default
        return hives[:3]  # Max 3 hives per task

    def _process_hive(self, hive, task, competitor, rag_context):
        """Process task through a single hive's clans."""
        clan_results = {}
        for clan_name, clan in hive["clans"].items():
            family_results = {}
            # Only process specialist + top3 families (not all 12)
            active_families = clan["families"][:4]  # specialist + top 3
            for fam in active_families:
                brain = self._get_brain(hive["name"], clan_name, fam)
                j_card = brain.process(task, competitor)
                family_results[fam] = j_card
            # Build clan C-space
            c_space = self._build_clan_cspace(clan_name, family_results)
            clan["c_space"] = c_space
            clan_results[clan_name] = {
                "clan_id": clan["id"],
                "specialist": clan["specialist"],
                "family_results": family_results,
                "c_space": c_space,
                "confidence": c_space["confidence"],
            }
        return clan_results

    def _build_clan_cspace(self, clan_name, family_results):
        best_fam = None
        best_conf = 0
        families = {}
        for fam, j_card in family_results.items():
            conf = j_card["confidence"]
            families[fam] = {"confidence": conf, "layer": j_card["routed"]["selected_layer"]}
            if conf > best_conf:
                best_conf = conf
                best_fam = fam
        return {"clan": clan_name, "families": families, "best_family": best_fam, "confidence": best_conf}

    def _aggregate_cspace(self, all_results):
        """Aggregate all hive results into master C-space."""
        master = {"hives": {}, "total_confidence": 0, "count": 0, "best_hive": None, "best_clan": None}
        best_conf = 0
        for hive_name, clan_results in all_results.items():
            hive_cspace = {"clans": {}, "confidence": 0, "count": 0}
            for clan_name, clan_result in clan_results.items():
                hive_cspace["clans"][clan_name] = clan_result["confidence"]
                hive_cspace["confidence"] += clan_result["confidence"]
                hive_cspace["count"] += 1
                master["total_confidence"] += clan_result["confidence"]
                master["count"] += 1
                if clan_result["confidence"] > best_conf:
                    best_conf = clan_result["confidence"]
                    master["best_clan"] = clan_name
                    master["best_hive"] = hive_name
            hive_cspace["avg_confidence"] = hive_cspace["confidence"] / max(hive_cspace["count"], 1)
            master["hives"][hive_name] = hive_cspace
        master["avg_confidence"] = master["total_confidence"] / max(master["count"], 1)
        return master

    def learn(self, outcome):
        """Feed outcome back into cached brains only."""
        for key, brain in self._brain_cache.items():
            brain.learn(outcome)

    def get_status(self):
        total_clans = sum(len(h["clans"]) for h in self.hives.values())
        total_brains = sum(len(h["clans"]) * 12 for h in self.hives.values())
        return {
            "hives": len(self.hives),
            "total_clans": total_clans,
            "total_brains": total_brains,
            "total_models": total_brains * 4,
            "tasks_processed": len(self.task_log),
            "stigmergy": self.stigmergy.get_status(),
            "cached_brains": len(self._brain_cache),
        }

    def get_topology(self):
        return {
            "hives": {name: {"clans": len(h["clans"]), "specialist": h["specialist"]} for name, h in self.hives.items()},
            "total_clans": sum(len(h["clans"]) for h in self.hives.values()),
            "total_brains": sum(len(h["clans"]) * 12 for h in self.hives.values()),
            "total_models": sum(len(h["clans"]) * 12 * 4 for h in self.hives.values()),
            "cached_brains": len(self._brain_cache),
        }

    def run_pdca(self, task):
        """PDCA interface for OWM compatibility."""
        result = self.process(task)
        return {
            "cycle": 1,
            "strategy": result.get("master_cspace", {}).get("best_clan", "reasoning"),
            "confidence": result.get("master_cspace", {}).get("avg_confidence", 0.5),
            "alliance": list(result.get("master_cspace", {}).get("hives", {}).keys()),
            "plan": {"selected_hives": list(result.get("master_cspace", {}).get("hives", {}).keys()), "task_type": "general"},
            "check": {"quorum": {"winning_clan": result.get("master_cspace", {}).get("best_clan", "reasoning")}},
            "act": {"alliance_updated": [], "gnn_updated": True, "honey_memory_updated": True, "recommendations": []},
        }

    def receive_outcome(self, task, won, details=None):
        """Receive outcome for OWM compatibility."""
        self.learn({"task": task.get("description", str(task)), "won": won})
