"""
OWEM SANDWICH BRAIN: 4-Layer Fractal Brain Structure

Each OWEM is a sandwich brain split into 4 layers:

    ┌─────────────────────────┐
    │   OWM-FROZEN (10%)      │  ← External interface, static weights
    │   OWM-FLUID  (10%)      │  ← External interface, honey-trained
    ├─────────────────────────┤
    │   IWM-FROZEN (40%)      │  ← Internal simulation, static weights
    │   IWM-FLUID  (40%)      │  ← Internal simulation, honey-trained
    └─────────────────────────┘

Each OWEM has a mini-SOV router (SOV1 or SOV2) that:
- Routes tasks between OWM and IWM layers
- Converts between frozen and fluid modes
- Feeds results into J-space cards
- Aggregates into C-space for BFT quorum

The OWM layers are small (10% each) — they handle external interface.
The IWM layers are big (40% each) — they do the heavy simulation.
"""
import json, hashlib
from pathlib import Path
from datetime import datetime
from .g_space import GSpace, FAMILIES, FAMILY_CAPABILITIES
from .j_space import JSpace
from .iwm import IWM
from .owm import OWM

IWM_DIR = Path(__file__).resolve().parent


class OWEMBrain:
    """OWEM Sandwich Brain: 4-layer fractal brain."""

    def __init__(self, family, clan_id=0):
        self.family = family
        self.clan_id = clan_id
        self.uid = f"owem-{clan_id}-{family}"

        # TOP SMALL (10% each) — OWM layers
        self.owm_frozen = OWMBrainLayer(family, mode="frozen", layer_type="owm")
        self.owm_fluid = OWMBrainLayer(family, mode="fluid", layer_type="owm")

        # BOTTOM BIG (40% each) — IWM layers
        self.iwm_frozen = OWMBrainLayer(family, mode="frozen", layer_type="iwm")
        self.iwm_fluid = OWMBrainLayer(family, mode="fluid", layer_type="iwm")

        # Mini-SOV router
        self.sov_router = MiniSOVRouter(self)

        # J-space cards (outputs from each layer)
        self.j_cards = []

    def process(self, task, competitor=None):
        """Process a task through all 4 layers of the sandwich brain."""
        results = {}
        # OWM layers (external interface — small, fast)
        results["owm_frozen"] = self.owm_frozen.process(task, competitor)
        results["owm_fluid"] = self.owm_fluid.process(task, competitor)
        # IWM layers (internal simulation — big, deep)
        results["iwm_frozen"] = self.iwm_frozen.process(task, competitor)
        results["iwm_fluid"] = self.iwm_fluid.process(task, competitor)
        # SOV router picks best result from all 4 layers
        routed = self.sov_router.route(results, task)
        # Create J-space card
        j_card = {
            "uid": self.uid,
            "family": self.family,
            "clan_id": self.clan_id,
            "task": task,
            "layer_results": results,
            "routed": routed,
            "confidence": routed["confidence"],
            "timestamp": datetime.now().isoformat(),
        }
        self.j_cards.append(j_card)
        return j_card

    def learn(self, outcome):
        """Feed outcome back into fluid layers for learning."""
        self.owm_fluid.learn(outcome)
        self.iwm_fluid.learn(outcome)
        self.sov_router.update_bias(outcome)

    def get_status(self):
        return {
            "uid": self.uid,
            "family": self.family,
            "clan_id": self.clan_id,
            "owm_frozen": self.owm_frozen.get_status(),
            "owm_fluid": self.owm_fluid.get_status(),
            "iwm_frozen": self.iwm_frozen.get_status(),
            "iwm_fluid": self.iwm_fluid.get_status(),
            "j_cards": len(self.j_cards),
            "router_bias": self.sov_router.bias,
        }


class OWMBrainLayer:
    """Single layer of the OWEM sandwich brain."""

    def __init__(self, family, mode="frozen", layer_type="owm"):
        self.family = family
        self.mode = mode
        self.layer_type = layer_type  # "owm" or "iwm"
        self.j_space = JSpace(family, mode=mode)
        self.process_count = 0
        self.learn_count = 0

    def process(self, task, competitor=None):
        """Process task through this layer."""
        self.process_count += 1
        comp_name = competitor.get("name", "unknown") if isinstance(competitor, dict) else str(competitor or "unknown")
        sim = self.j_space.simulate_competitor(comp_name, task)
        return {
            "layer": f"{self.layer_type}_{self.mode}",
            "family": self.family,
            "confidence": sim["confidence"],
            "approach": sim["approach"],
            "strengths": sim["strengths"],
            "weaknesses": sim["weaknesses"],
            "counter_strategy": sim["counter_strategy"],
        }

    def learn(self, outcome):
        """Learn from outcome (fluid mode only)."""
        if self.mode == "fluid":
            self.learn_count += 1
            self.j_space.learn_from_outcome(
                task=outcome.get("task", ""),
                won=outcome.get("won", False),
                competitor=outcome.get("competitor", "unknown"),
                strategy_used=outcome.get("strategy", {"primary": "default"}),
            )

    def get_status(self):
        return {
            "family": self.family,
            "mode": self.mode,
            "layer_type": self.layer_type,
            "process_count": self.process_count,
            "learn_count": self.learn_count,
            "knowledge_entries": len(self.j_space.knowledge),
            "honey_entries": len(self.j_space.honey_memory.get("entries", [])),
        }


class MiniSOVRouter:
    """Mini-SOV router: routes between the 4 layers of an OWEM brain."""

    def __init__(self, brain):
        self.brain = brain
        self.bias = {
            "owm_frozen": 0.25,
            "owm_fluid": 0.25,
            "iwm_frozen": 0.25,
            "iwm_fluid": 0.25,
        }

    def route(self, layer_results, task):
        """Route to best layer based on confidence + bias."""
        best_layer = None
        best_score = -1
        for layer_name, result in layer_results.items():
            score = result["confidence"] * self.bias.get(layer_name, 0.25)
            if score > best_score:
                best_score = score
                best_layer = layer_name
        return {
            "selected_layer": best_layer,
            "confidence": best_score,
            "all_scores": {k: v["confidence"] * self.bias.get(k, 0.25) for k, v in layer_results.items()},
        }

    def update_bias(self, outcome):
        """Update routing bias based on outcome."""
        if outcome.get("won"):
            layer = outcome.get("layer", "iwm_fluid")
            self.bias[layer] = min(self.bias.get(layer, 0.25) + 0.05, 0.5)
            # Normalize
            total = sum(self.bias.values())
            self.bias = {k: v / total for k, v in self.bias.items()}
