"""
J-SPACE: Per-Family Competitive Simulation

Each family has its own J-space that can:
1. Run frozen inference (base model weights)
2. Run fluid inference (honey-trained variant)
3. Simulate a competitor's approach
4. Generate counter-strategies

J-spaces are spawned by the Clan Engine and report to G-space.
"""
import json, hashlib, time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
EAT_DIR = ROOT / "eat_results"
IWM_DIR = ROOT / "iwms"

STRIP_THINK = None
try:
    import re
    STRIP_THINK = re.compile(r"<think>.*?</think>|<thinking>.*?</thinking>", re.IGNORECASE | re.DOTALL)
except ImportError:
    pass


class JSpace:
    """J-space: Per-family simulation environment."""

    def __init__(self, family, mode="frozen"):
        self.family = family
        self.mode = mode  # "frozen" or "fluid"
        self.knowledge = self._load_knowledge()
        self.simulation_log = []
        self.honey_memory = self._load_honey()

    def _load_knowledge(self):
        """Load family's EAT knowledge."""
        path = EAT_DIR / f"extract_{self.family}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        # Try free_gpu_eat_all
        path = EAT_DIR / "free_gpu_eat_all.json"
        if path.exists():
            try:
                all_entries = json.loads(path.read_text())
                return [e for e in all_entries if e.get("family") == self.family and e.get("ok")]
            except Exception:
                pass
        return []

    def _load_honey(self):
        """Load honey-trained memory (fluid mode)."""
        path = IWM_DIR / f"honey_{self.family}.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {"entries": [], "win_patterns": {}, "strategy_scores": {}}

    def save_honey(self):
        path = IWM_DIR / f"honey_{self.family}.json"
        path.write_text(json.dumps(self.honey_memory, indent=2))

    def _normalize_task(self, task):
        if isinstance(task, dict):
            return task.get("description", str(task))
        return str(task)

    def simulate_competitor(self, competitor_description, task):
        """Simulate how a competitor would approach a task."""
        task = self._normalize_task(task)
        # Find relevant knowledge
        relevant = self._find_relevant_knowledge(task)
        # Generate competitor simulation
        simulation = {
            "family": self.family,
            "mode": self.mode,
            "competitor": competitor_description,
            "task": task,
            "relevant_knowledge": len(relevant),
            "approach": self._generate_approach(task, relevant),
            "strengths": self._identify_strengths(task),
            "weaknesses": self._identify_weaknesses(task),
            "counter_strategy": self._generate_counter_strategy(task, competitor_description),
            "confidence": self._compute_confidence(relevant),
            "timestamp": datetime.now().isoformat(),
        }
        self.simulation_log.append(simulation)
        return simulation

    def _find_relevant_knowledge(self, task):
        """Find knowledge entries relevant to the task."""
        if isinstance(task, dict):
            task = task.get("description", str(task))
        task_lower = task.lower()
        relevant = []
        for entry in self.knowledge:
            q = entry.get("q", "").lower()
            a = entry.get("a", "").lower()
            # Simple keyword overlap
            task_words = set(task_lower.split())
            entry_words = set((q + " " + a).split())
            overlap = task_words & entry_words
            if len(overlap) >= 2:
                relevant.append(entry)
        # Also check honey memory
        for entry in self.honey_memory.get("entries", []):
            if any(w in entry.get("context", "").lower() for w in task_lower.split()[:5]):
                relevant.append(entry)
        return relevant[:10]

    def _generate_approach(self, task, knowledge):
        """Generate approach based on family's knowledge and mode."""
        if self.mode == "fluid" and self.honey_memory.get("win_patterns"):
            # Use learned patterns
            best_pattern = max(
                self.honey_memory["win_patterns"].items(),
                key=lambda x: x[1].get("score", 0),
                default=("default", {"score": 0})
            )
            return {
                "strategy": best_pattern[0],
                "source": "honey_memory",
                "score": best_pattern[1].get("score", 0),
            }
        # Frozen mode: use EAT knowledge
        if knowledge:
            return {
                "strategy": f"Leverage {self.family} knowledge ({len(knowledge)} entries)",
                "source": "eat_knowledge",
                "key_insights": [e.get("q", "") for e in knowledge[:3]],
            }
        return {"strategy": f"Default {self.family} approach", "source": "default"}

    def _identify_strengths(self, task):
        """Identify family's strengths for this task type."""
        task = self._normalize_task(task)
        from .g_space import FAMILY_CAPABILITIES
        caps = FAMILY_CAPABILITIES.get(self.family, {})
        task_lower = task.lower()
        strengths = []
        if "code" in task_lower and caps.get("coding", 0) > 0.8:
            strengths.append("coding")
        if "reason" in task_lower and caps.get("reasoning", 0) > 0.8:
            strengths.append("reasoning")
        if "math" in task_lower and caps.get("math", 0) > 0.8:
            strengths.append("math")
        if "vision" in task_lower and caps.get("vision", 0) > 0.8:
            strengths.append("vision")
        if "translat" in task_lower and caps.get("multilingual", 0) > 0.8:
            strengths.append("multilingual")
        return strengths if strengths else ["general"]

    def _identify_weaknesses(self, task):
        """Identify family's weaknesses for this task type."""
        task = self._normalize_task(task)
        from .g_space import FAMILY_CAPABILITIES
        caps = FAMILY_CAPABILITIES.get(self.family, {})
        task_lower = task.lower()
        weaknesses = []
        if "code" in task_lower and caps.get("coding", 0) < 0.6:
            weaknesses.append("coding")
        if "reason" in task_lower and caps.get("reasoning", 0) < 0.6:
            weaknesses.append("reasoning")
        if "math" in task_lower and caps.get("math", 0) < 0.6:
            weaknesses.append("math")
        if "vision" in task_lower and caps.get("vision", 0) < 0.6:
            weaknesses.append("vision")
        return weaknesses if weaknesses else ["none_identified"]

    def _generate_counter_strategy(self, task, competitor):
        """Generate a counter-strategy against the competitor."""
        strategies = [
            f"Exploit {self.family}'s strength in areas {competitor} is weak",
            f"Use {self.family}'s broader knowledge base for edge cases",
            f"Leverage {self.family}'s speed advantage for time-critical tasks",
            f"Apply {self.family}'s multilingual capabilities for diverse inputs",
            f"Use {self.family}'s tool use for complex multi-step tasks",
        ]
        if self.mode == "fluid" and self.honey_memory.get("strategy_scores"):
            best = max(self.honey_memory["strategy_scores"].items(),
                      key=lambda x: x[1], default=("default", 0))
            return {"primary": best[0], "alternatives": strategies[:3], "source": "honey"}
        return {"primary": strategies[0], "alternatives": strategies[1:3], "source": "frozen"}

    def _compute_confidence(self, knowledge):
        """Compute confidence score based on available knowledge."""
        base = min(len(knowledge) / 10.0, 1.0)
        if self.mode == "fluid":
            honey_bonus = min(len(self.honey_memory.get("entries", [])) / 20.0, 0.3)
            return min(base + honey_bonus, 1.0)
        return base

    def learn_from_outcome(self, task, won, competitor, strategy_used):
        """Update honey memory based on arena outcome."""
        entry = {
            "task": task,
            "won": won,
            "competitor": competitor,
            "strategy": strategy_used,
            "timestamp": datetime.now().isoformat(),
        }
        self.honey_memory["entries"].append(entry)
        # Update win patterns
        pattern_key = strategy_used.get("primary", "default")
        if pattern_key not in self.honey_memory["win_patterns"]:
            self.honey_memory["win_patterns"][pattern_key] = {"wins": 0, "losses": 0, "score": 0.5}
        if won:
            self.honey_memory["win_patterns"][pattern_key]["wins"] += 1
        else:
            self.honey_memory["win_patterns"][pattern_key]["losses"] += 1
        total = (self.honey_memory["win_patterns"][pattern_key]["wins"] +
                self.honey_memory["win_patterns"][pattern_key]["losses"])
        self.honey_memory["win_patterns"][pattern_key]["score"] = (
            self.honey_memory["win_patterns"][pattern_key]["wins"] / total if total > 0 else 0.5
        )
        # Update strategy scores
        if won:
            self.honey_memory["strategy_scores"][pattern_key] = (
                self.honey_memory["strategy_scores"].get(pattern_key, 0.5) + 0.05
            )
        else:
            self.honey_memory["strategy_scores"][pattern_key] = max(
                self.honey_memory["strategy_scores"].get(pattern_key, 0.5) - 0.05, 0.0
            )
        self.save_honey()

    def get_status(self):
        return {
            "family": self.family,
            "mode": self.mode,
            "knowledge_entries": len(self.knowledge),
            "honey_entries": len(self.honey_memory.get("entries", [])),
            "win_patterns": len(self.honey_memory.get("win_patterns", {})),
            "simulations_run": len(self.simulation_log),
        }
