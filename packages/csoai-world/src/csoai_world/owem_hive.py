"""
OWEM HIVE: 12-Clan Fractal Hive Structure

The hive is 12 clan layers, each containing 4 specialist families.
Each family is an OWEM sandwich brain (4 layers).

    SOV SPACE
    ├── CLAN LAYER 1: REASONING (deepseek, qwen, llama, nemotron)
    │   ├── OWEM-Brain: deepseek
    │   ├── OWEM-Brain: qwen
    │   ├── OWEM-Brain: llama
    │   └── OWEM-Brain: nemotron
    ├── CLAN LAYER 2: CODING (code, deepseek, qwen, mistral)
    │   ├── OWEM-Brain: code
    │   ...
    ├── CLAN LAYER 3: VISION (vision, qwen-vision, gemma, MiniMax)
    ├── CLAN LAYER 4: MULTILINGUAL (qwen, mistral, llama, MiniMax)
    ├── CLAN LAYER 5: MATH (deepseek, phi, nemotron, qwen)
    ├── CLAN LAYER 6: SAFETY (gemma, llama, core, compliance)
    ├── CLAN LAYER 7: CREATIVE (llama, qwen, mistral, gpt-oss)
    ├── CLAN LAYER 8: KNOWLEDGE (research, core, arch, deepseek)
    ├── CLAN LAYER 9: TOOL_USE (code, qwen, mistral, infra)
    ├── CLAN LAYER 10: EDGE (phi, gemma, embedding, distribution)
    ├── CLAN LAYER 11: COMPLIANCE (compliance, core, research, arch)
    └── CLAN LAYER 12: INFRA (infra, distribution, code, gpt-oss)

Each clan layer has:
- 4 OWEM sandwich brains (one per specialist family)
- A clan-level SOV router
- A clan C-space (composite of 4 J-spaces)
- Stigmergy connections to other clans
"""
import json
from pathlib import Path
from datetime import datetime
from .owem_brain import OWEMBrain

IWM_DIR = Path(__file__).resolve().parent

CLAN_LAYERS = {
    "reasoning": {"families": ["deepseek", "qwen", "llama", "nemotron"], "specialist": "deepseek"},
    "coding": {"families": ["code", "deepseek", "qwen", "mistral"], "specialist": "code"},
    "vision": {"families": ["vision", "qwen-vision", "gemma", "MiniMax"], "specialist": "vision"},
    "multilingual": {"families": ["qwen", "mistral", "llama", "MiniMax"], "specialist": "qwen"},
    "math": {"families": ["deepseek", "phi", "nemotron", "qwen"], "specialist": "deepseek"},
    "safety": {"families": ["gemma", "llama", "core", "compliance"], "specialist": "gemma"},
    "creative": {"families": ["llama", "qwen", "mistral", "gpt-oss"], "specialist": "llama"},
    "knowledge": {"families": ["research", "core", "arch", "deepseek"], "specialist": "research"},
    "tool_use": {"families": ["code", "qwen", "mistral", "infra"], "specialist": "code"},
    "edge": {"families": ["phi", "gemma", "embedding", "distribution"], "specialist": "phi"},
    "compliance": {"families": ["compliance", "core", "research", "arch"], "specialist": "compliance"},
    "infrastructure": {"families": ["infra", "distribution", "code", "gpt-oss"], "specialist": "infra"},
}


class OWEMHive:
    """OWEM Hive: 12-clan fractal hive structure."""

    def __init__(self):
        self.clans = {}
        self.stigmergy = StigmergyLayer()
        self._build_hive()

    def _build_hive(self):
        """Build all 12 clan layers with their OWEM brains."""
        for clan_id, (clan_name, config) in enumerate(CLAN_LAYERS.items()):
            families = config["families"]
            specialist = config["specialist"]
            brains = {}
            for fam in families:
                brains[fam] = OWEMBrain(family=fam, clan_id=clan_id)
            self.clans[clan_name] = {
                "id": clan_id,
                "name": clan_name,
                "specialist": specialist,
                "families": families,
                "brains": brains,
                "c_space": {},
            }

    def process_task(self, task, competitor=None, target_clans=None):
        """
        Process a task through the hive.
        
        If target_clans specified, only those clans process it.
        Otherwise, all clans process it (full swarm).
        """
        if target_clans is None:
            target_clans = list(self.clans.keys())
        results = {}
        for clan_name in target_clans:
            clan = self.clans[clan_name]
            clan_results = {}
            for fam, brain in clan["brains"].items():
                j_card = brain.process(task, competitor)
                clan_results[fam] = j_card
            # Build clan C-space
            c_space = self._build_clan_cspace(clan_name, clan_results)
            clan["c_space"] = c_space
            results[clan_name] = {
                "clan_id": clan["id"],
                "specialist": clan["specialist"],
                "family_results": clan_results,
                "c_space": c_space,
                "best_family": c_space["best_family"],
                "confidence": c_space["confidence"],
            }
        # Stigmergy: propagate signals between clans
        self.stigmergy.propagate(results)
        return results

    def _build_clan_cspace(self, clan_name, clan_results):
        """Build C-space for a single clan (composite of4 family J-spaces)."""
        best_fam = None
        best_conf = 0
        families = {}
        for fam, j_card in clan_results.items():
            conf = j_card["confidence"]
            families[fam] = {
                "confidence": conf,
                "layer": j_card["routed"]["selected_layer"],
                "strengths": j_card["layer_results"][j_card["routed"]["selected_layer"]]["strengths"],
            }
            if conf > best_conf:
                best_conf = conf
                best_fam = fam
        return {
            "clan": clan_name,
            "families": families,
            "best_family": best_fam,
            "confidence": best_conf,
        }

    def learn_from_outcome(self, clan_name, family, outcome):
        """Feed outcome back into specific OWEM brain."""
        if clan_name in self.clans and family in self.clans[clan_name]["brains"]:
            self.clans[clan_name]["brains"][family].learn(outcome)

    def get_hive_status(self):
        """Get status of the entire hive."""
        status = {}
        for clan_name, clan in self.clans.items():
            status[clan_name] = {
                "id": clan["id"],
                "specialist": clan["specialist"],
                "families": clan["families"],
                "brain_status": {fam: brain.get_status() for fam, brain in clan["brains"].items()},
            }
        return status

    def get_topology(self):
        """Get hive topology for visualization."""
        return {
            "total_clans": len(self.clans),
            "total_brains": sum(len(c["brains"]) for c in self.clans.values()),
            "total_layers": sum(len(c["brains"]) * 4 for c in self.clans.values()),
            "clans": {name: {"families": c["families"], "specialist": c["specialist"]} for name, c in self.clans.items()},
        }


class StigmergyLayer:
    """Stigmergy: pheromone-like connections between all OWEMs."""

    def __init__(self):
        self.signals = []
        self.pheromone_trails = {}

    def propagate(self, clan_results):
        """Propagate signals between clans based on results."""
        for clan_name, result in clan_results.items():
            signal = {
                "source_clan": clan_name,
                "confidence": result["confidence"],
                "best_family": result["best_family"],
                "timestamp": datetime.now().isoformat(),
            }
            self.signals.append(signal)
            # Update pheromone trail
            key = f"{clan_name}:{result['best_family']}"
            if key not in self.pheromone_trails:
                self.pheromone_trails[key] = {"strength": 0, "count": 0}
            self.pheromone_trails[key]["strength"] += result["confidence"]
            self.pheromone_trails[key]["count"] += 1

    def get_strongest_trails(self, top_n=10):
        """Get the strongest pheromone trails (most successful clan:family combos)."""
        sorted_trails = sorted(
            self.pheromone_trails.items(),
            key=lambda x: x[1]["strength"] / max(x[1]["count"], 1),
            reverse=True,
        )
        return sorted_trails[:top_n]

    def get_signal_summary(self):
        """Get summary of stigmergy signals."""
        return {
            "total_signals": len(self.signals),
            "active_trails": len(self.pheromone_trails),
            "strongest_trails": self.get_strongest_trails(5),
        }
