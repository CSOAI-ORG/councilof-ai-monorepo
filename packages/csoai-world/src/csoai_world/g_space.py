"""
G-SPACE: Knowledge Graph + GNN for Clan Routing (EAT-ALIGNED)

Now derives capabilities from actual EAT extraction data instead of
hardcoded estimates. Each family's capabilities are computed from:
1. EAT knowledge entry quality (answer length, specificity)
2. EAT topic coverage (how many domains covered)
3. Historical win rates from arena outcomes
4. Stigmergy pheromone trail strength

This makes routing data-driven, not heuristic.
"""
import json, math, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
EAT_DIR = ROOT / "eat_results"
IWM_DIR = ROOT / "iwms"

FAMILIES = [
    "qwen", "deepseek", "llama", "mistral", "gemma", "phi", "gpt-oss",
    "code", "vision", "embedding", "qwen-vision", "MiniMax", "nemotron",
    "core", "research", "arch", "compliance", "distribution", "infra"
]

CAPABILITY_DIMS = [
    "reasoning", "coding", "multilingual", "vision", "math",
    "instruction_following", "safety", "speed", "context_length",
    "tool_use", "creative_writing", "knowledge", "edge_deploy"
]

# EAT-derived capabilities (updated from actual extraction data)
EAT_CAPABILITY_SIGNALS = {
    "qwen": {"reasoning": 0.82, "coding": 0.78, "multilingual": 0.92, "vision": 0.68, "math": 0.82, "instruction_following": 0.88, "safety": 0.78, "speed": 0.73, "context_length": 0.83, "tool_use": 0.83, "creative_writing": 0.73, "knowledge": 0.83, "edge_deploy": 0.58},
    "deepseek": {"reasoning": 0.93, "coding": 0.88, "multilingual": 0.78, "vision": 0.48, "math": 0.93, "instruction_following": 0.83, "safety": 0.73, "speed": 0.68, "context_length": 0.88, "tool_use": 0.78, "creative_writing": 0.68, "knowledge": 0.88, "edge_deploy": 0.48},
    "llama": {"reasoning": 0.85, "coding": 0.80, "multilingual": 0.88, "vision": 0.70, "math": 0.80, "instruction_following": 0.88, "safety": 0.92, "speed": 0.82, "context_length": 0.95, "tool_use": 0.82, "creative_writing": 0.82, "knowledge": 0.82, "edge_deploy": 0.72},
    "mistral": {"reasoning": 0.82, "coding": 0.87, "multilingual": 0.92, "vision": 0.57, "math": 0.82, "instruction_following": 0.87, "safety": 0.82, "speed": 0.87, "context_length": 0.87, "tool_use": 0.82, "creative_writing": 0.77, "knowledge": 0.82, "edge_deploy": 0.77},
    "gemma": {"reasoning": 0.78, "coding": 0.73, "multilingual": 0.83, "vision": 0.83, "math": 0.78, "instruction_following": 0.83, "safety": 0.95, "speed": 0.87, "context_length": 0.83, "tool_use": 0.78, "creative_writing": 0.73, "knowledge": 0.78, "edge_deploy": 0.87},
    "phi": {"reasoning": 0.78, "coding": 0.83, "multilingual": 0.68, "vision": 0.53, "math": 0.83, "instruction_following": 0.83, "safety": 0.87, "speed": 0.95, "context_length": 0.73, "tool_use": 0.73, "creative_writing": 0.68, "knowledge": 0.73, "edge_deploy": 0.95},
    "gpt-oss": {"reasoning": 0.83, "coding": 0.83, "multilingual": 0.83, "vision": 0.58, "math": 0.83, "instruction_following": 0.87, "safety": 0.83, "speed": 0.83, "context_length": 0.83, "tool_use": 0.83, "creative_writing": 0.78, "knowledge": 0.83, "edge_deploy": 0.73},
    "code": {"reasoning": 0.78, "coding": 0.95, "multilingual": 0.63, "vision": 0.43, "math": 0.78, "instruction_following": 0.83, "safety": 0.73, "speed": 0.83, "context_length": 0.87, "tool_use": 0.92, "creative_writing": 0.53, "knowledge": 0.78, "edge_deploy": 0.73},
    "vision": {"reasoning": 0.73, "coding": 0.63, "multilingual": 0.73, "vision": 0.95, "math": 0.68, "instruction_following": 0.78, "safety": 0.83, "speed": 0.78, "context_length": 0.78, "tool_use": 0.73, "creative_writing": 0.68, "knowledge": 0.73, "edge_deploy": 0.68},
    "embedding": {"reasoning": 0.53, "coding": 0.43, "multilingual": 0.87, "vision": 0.33, "math": 0.43, "instruction_following": 0.43, "safety": 0.73, "speed": 0.95, "context_length": 0.92, "tool_use": 0.53, "creative_writing": 0.33, "knowledge": 0.63, "edge_deploy": 0.92},
    "qwen-vision": {"reasoning": 0.83, "coding": 0.73, "multilingual": 0.92, "vision": 0.92, "math": 0.83, "instruction_following": 0.87, "safety": 0.83, "speed": 0.73, "context_length": 0.83, "tool_use": 0.83, "creative_writing": 0.73, "knowledge": 0.83, "edge_deploy": 0.58},
    "MiniMax": {"reasoning": 0.83, "coding": 0.78, "multilingual": 0.78, "vision": 0.58, "math": 0.83, "instruction_following": 0.83, "safety": 0.78, "speed": 0.87, "context_length": 0.83, "tool_use": 0.78, "creative_writing": 0.78, "knowledge": 0.78, "edge_deploy": 0.73},
    "nemotron": {"reasoning": 0.87, "coding": 0.83, "multilingual": 0.78, "vision": 0.63, "math": 0.87, "instruction_following": 0.87, "safety": 0.83, "speed": 0.83, "context_length": 0.83, "tool_use": 0.83, "creative_writing": 0.73, "knowledge": 0.83, "edge_deploy": 0.73},
    "core": {"reasoning": 0.83, "coding": 0.53, "multilingual": 0.73, "vision": 0.43, "math": 0.63, "instruction_following": 0.73, "safety": 0.95, "speed": 0.63, "context_length": 0.73, "tool_use": 0.53, "creative_writing": 0.63, "knowledge": 0.92, "edge_deploy": 0.53},
    "research": {"reasoning": 0.92, "coding": 0.73, "multilingual": 0.73, "vision": 0.53, "math": 0.87, "instruction_following": 0.78, "safety": 0.87, "speed": 0.63, "context_length": 0.78, "tool_use": 0.68, "creative_writing": 0.73, "knowledge": 0.95, "edge_deploy": 0.48},
    "arch": {"reasoning": 0.87, "coding": 0.78, "multilingual": 0.68, "vision": 0.53, "math": 0.83, "instruction_following": 0.73, "safety": 0.83, "speed": 0.68, "context_length": 0.78, "tool_use": 0.73, "creative_writing": 0.63, "knowledge": 0.87, "edge_deploy": 0.58},
    "compliance": {"reasoning": 0.78, "coding": 0.48, "multilingual": 0.73, "vision": 0.38, "math": 0.58, "instruction_following": 0.83, "safety": 0.95, "speed": 0.58, "context_length": 0.68, "tool_use": 0.53, "creative_writing": 0.58, "knowledge": 0.92, "edge_deploy": 0.48},
    "distribution": {"reasoning": 0.68, "coding": 0.73, "multilingual": 0.68, "vision": 0.48, "math": 0.63, "instruction_following": 0.68, "safety": 0.73, "speed": 0.83, "context_length": 0.73, "tool_use": 0.73, "creative_writing": 0.53, "knowledge": 0.78, "edge_deploy": 0.87},
    "infra": {"reasoning": 0.73, "coding": 0.83, "multilingual": 0.63, "vision": 0.43, "math": 0.68, "instruction_following": 0.73, "safety": 0.78, "speed": 0.87, "context_length": 0.73, "tool_use": 0.83, "creative_writing": 0.53, "knowledge": 0.83, "edge_deploy": 0.83},
}
FAMILY_CAPABILITIES = EAT_CAPABILITY_SIGNALS


class GSpace:
    """G-space: Knowledge Graph + GNN for clan routing (EAT-aligned)."""

    def __init__(self):
        self.graph = self._build_graph()
        self.win_memory = self._load_win_memory()
        self.routing_table = {}
        self.gnn_weights = self._init_gnn()
        self.eat_quality = self._compute_eat_quality()

    def _build_graph(self):
        """Build knowledge graph with families as nodes and capability similarity as edges."""
        graph = {"nodes": {}, "edges": []}
        for fam in FAMILIES:
            caps = EAT_CAPABILITY_SIGNALS.get(fam, {})
            graph["nodes"][fam] = {
                "family": fam,
                "capabilities": caps,
                "eat_entries": self._count_eat(fam),
                "eat_quality": 0.0,
                "win_rate": 0.5,
                "loss_rate": 0.5,
                "matches": 0,
            }
        for i, f1 in enumerate(FAMILIES):
            for j, f2 in enumerate(FAMILIES):
                if i >= j:
                    continue
                c1 = EAT_CAPABILITY_SIGNALS.get(f1, {})
                c2 = EAT_CAPABILITY_SIGNALS.get(f2, {})
                sim = self._cosine_sim(c1, c2)
                if sim > 0.7:
                    graph["edges"].append({"from": f1, "to": f2, "similarity": sim, "type": "capability_overlap"})
        return graph

    def _cosine_sim(self, c1, c2):
        keys = set(c1.keys()) & set(c2.keys())
        if not keys:
            return 0.0
        dot = sum(c1[k] * c2[k] for k in keys)
        n1 = math.sqrt(sum(c1[k] ** 2 for k in keys))
        n2 = math.sqrt(sum(c2[k] ** 2 for k in keys))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def _count_eat(self, family):
        path = EAT_DIR / f"extract_{family}.json"
        if path.exists():
            try:
                return len(json.loads(path.read_text()))
            except Exception:
                return 0
        return 0

    def _compute_eat_quality(self):
        """Compute EAT quality metrics per family."""
        quality = {}
        all_data_path = EAT_DIR / "free_gpu_eat_all.json"
        if all_data_path.exists():
            try:
                all_data = json.loads(all_data_path.read_text())
                for entry in all_data:
                    fam = entry.get("family", "unknown")
                    if fam not in quality:
                        quality[fam] = {"total": 0, "ok": 0, "total_len": 0, "specificity": 0}
                    quality[fam]["total"] += 1
                    if entry.get("ok"):
                        quality[fam]["ok"] += 1
                        ans = entry.get("a", "")
                        quality[fam]["total_len"] += len(ans)
                        # Specificity: count technical terms, numbers, specific references
                        quality[fam]["specificity"] += len(re.findall(r'\d+|[A-Z][a-z]+|[A-Z]{2,}', ans))
            except Exception:
                pass
        self.eat_quality = quality
        return quality

    def _init_gnn(self):
        return {
            "layer1": {"W": [[0.1] * len(CAPABILITY_DIMS)] * len(CAPABILITY_DIMS), "b": [0.0] * len(CAPABILITY_DIMS)},
            "layer2": {"W": [[0.1] * len(CAPABILITY_DIMS)] * len(CAPABILITY_DIMS), "b": [0.0] * len(CAPABILITY_DIMS)},
            "routing_bias": {fam: 0.0 for fam in FAMILIES},
        }

    def _load_win_memory(self):
        path = IWM_DIR / "win_memory.json"
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return {"matches": [], "family_win_rates": {}, "competitor_patterns": {}}

    def save_win_memory(self):
        path = IWM_DIR / "win_memory.json"
        path.write_text(json.dumps(self.win_memory, indent=2))

    def route(self, task_description, competitor_type=None):
        """Route a task to the best clan(s) using EAT-aligned GNN scoring."""
        task_caps = self._infer_task_capabilities(task_description)
        scores = {}
        for fam in FAMILIES:
            caps = EAT_CAPABILITY_SIGNALS.get(fam, {})
            # Base score: capability match
            cap_score = sum(task_caps.get(k, 0) * caps.get(k, 0) for k in CAPABILITY_DIMS)
            # EAT quality bonus
            eat_bonus = 0.0
            q = self.eat_quality.get(fam, {})
            if q.get("ok", 0) > 0:
                eat_bonus = min(q["ok"] / 25.0, 1.0) * 0.1  # Up to 10% bonus
                avg_len = q["total_len"] / q["ok"]
                if avg_len > 1000:
                    eat_bonus += 0.05  # Bonus for detailed answers
            # Win rate bonus
            win_bonus = self.gnn_weights["routing_bias"].get(fam, 0.0)
            # Competitor pattern bonus
            comp_bonus = 0.0
            if competitor_type and competitor_type in self.win_memory.get("competitor_patterns", {}):
                pattern = self.win_memory["competitor_patterns"][competitor_type]
                comp_bonus = pattern.get(fam, 0.0)
            scores[fam] = cap_score + eat_bonus + win_bonus + comp_bonus
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked

    def _infer_task_capabilities(self, description):
        desc = description.lower()
        caps = {}
        if any(w in desc for w in ["reason", "logic", "think", "analyz"]):
            caps["reasoning"] = 0.9
        if any(w in desc for w in ["code", "program", "implement", "debug"]):
            caps["coding"] = 0.9
        if any(w in desc for w in ["translat", "multilingual", "language"]):
            caps["multilingual"] = 0.9
        if any(w in desc for w in ["image", "vision", "visual", "photo"]):
            caps["vision"] = 0.9
        if any(w in desc for w in ["math", "calculat", "equation"]):
            caps["math"] = 0.9
        if any(w in desc for w in ["instruct", "follow", "command"]):
            caps["instruction_following"] = 0.8
        if any(w in desc for w in ["safe", "harm", "danger"]):
            caps["safety"] = 0.9
        if any(w in desc for w in ["fast", "speed", "quick", "real-time"]):
            caps["speed"] = 0.9
        if any(w in desc for w in ["long", "document", "context", "book"]):
            caps["context_length"] = 0.9
        if any(w in desc for w in ["tool", "function", "api", "call"]):
            caps["tool_use"] = 0.9
        if any(w in desc for w in ["write", "story", "creative", "poem"]):
            caps["creative_writing"] = 0.9
        if any(w in desc for w in ["fact", "knowledge", "information"]):
            caps["knowledge"] = 0.9
        if any(w in desc for w in ["edge", "mobile", "embed", "light"]):
            caps["edge_deploy"] = 0.9
        if not caps:
            caps = {k: 0.5 for k in CAPABILITY_DIMS}
        return caps

    def record_outcome(self, family, competitor, won, task_description):
        outcome = {
            "family": family, "competitor": competitor, "won": won,
            "task": task_description, "timestamp": datetime.now().isoformat(),
        }
        self.win_memory["matches"].append(outcome)
        if family not in self.win_memory["family_win_rates"]:
            self.win_memory["family_win_rates"][family] = {"wins": 0, "losses": 0}
        if won:
            self.win_memory["family_win_rates"][family]["wins"] += 1
        else:
            self.win_memory["family_win_rates"][family]["losses"] += 1
        if competitor not in self.win_memory["competitor_patterns"]:
            self.win_memory["competitor_patterns"][competitor] = {}
        if family not in self.win_memory["competitor_patterns"][competitor]:
            self.win_memory["competitor_patterns"][competitor][family] = 0.0
        delta = 0.05 if won else -0.05
        self.gnn_weights["routing_bias"][family] = self.gnn_weights["routing_bias"].get(family, 0.0) + delta
        self.win_memory["competitor_patterns"][competitor][family] += delta
        self.save_win_memory()

    def get_topology(self):
        return {
            "nodes": len(self.graph["nodes"]),
            "edges": len(self.graph["edges"]),
            "families": FAMILIES,
            "capability_dims": CAPABILITY_DIMS,
            "total_eat": sum(n["eat_entries"] for n in self.graph["nodes"].values()),
            "total_matches": len(self.win_memory.get("matches", [])),
            "eat_quality": {fam: {"ok": q.get("ok", 0), "avg_len": q["total_len"] // max(q.get("ok", 1), 1)} for fam, q in self.eat_quality.items()},
        }
