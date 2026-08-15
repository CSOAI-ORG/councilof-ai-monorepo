"""
ARENA INTEGRATION: Bootstrap from Arena.ai Leaderboard

Connects SOV to arena.ai to:
1. Fetch top model rankings and metrics
2. Learn from arena battle patterns
3. Bootstrap SOV's capabilities from top-tier models
4. Track SOV's performance against arena leaders
5. Use arena signals (success, praise, steerability, bash recovery, tool hallucination)

Arena Metrics (from leaderboard):
- Net Improvement: How much better than baseline
- Confirmed Success: Task completion rate
- Praise vs Complaint: User satisfaction
- Steerability: Handling user corrections
- Bash Recovery: Recovery from failed commands
- Tool Hallucination: False tool claims (lower is better)

Top Models (Jul 2026):
1. Claude Fable 5 (High) - 12.72% net improvement
2. GPT 5.6 Sol (xHigh) - 10.12% net improvement
3. Claude Opus 4.8 (Thinking) - 9.75% net improvement
4. Kimi K3 - 9.71% net improvement
5. Claude Sonnet 5 (High) - 8.66% net improvement
"""
import json, re
from pathlib import Path
from datetime import datetime

IWM_DIR = Path(__file__).resolve().parent
ARENA_CACHE = IWM_DIR / "arena_data.json"

# Arena leaderboard data (Jul 2026)
ARENA_LEADERBOARD = [
    {"rank": 1, "model": "Claude Fable 5 (High)", "provider": "Anthropic", "net_improvement": 12.72, "confirmed_success": 10.67, "praise_complaint": 23.94, "steerability": 14.62, "bash_recovery": 12.97, "tool_hallucination": 1.39, "sessions": 23549, "license": "Proprietary"},
    {"rank": 2, "model": "GPT 5.6 Sol (xHigh)", "provider": "OpenAI", "net_improvement": 10.12, "confirmed_success": 7.25, "praise_complaint": 23.53, "steerability": 9.71, "bash_recovery": 8.74, "tool_hallucination": 1.39, "sessions": 15991, "license": "Proprietary"},
    {"rank": 3, "model": "Claude Opus 4.8 (Thinking)", "provider": "Anthropic", "net_improvement": 9.75, "confirmed_success": 8.90, "praise_complaint": 19.42, "steerability": 9.78, "bash_recovery": 10.43, "tool_hallucination": 0.22, "sessions": 34147, "license": "Proprietary"},
    {"rank": 4, "model": "Kimi K3", "provider": "Moonshot", "net_improvement": 9.71, "confirmed_success": 14.00, "praise_complaint": 20.30, "steerability": 6.52, "bash_recovery": 6.33, "tool_hallucination": 1.39, "sessions": 11490, "license": "Proprietary"},
    {"rank": 5, "model": "Claude Sonnet 5 (High)", "provider": "Anthropic", "net_improvement": 8.66, "confirmed_success": 8.14, "praise_complaint": 16.88, "steerability": 6.20, "bash_recovery": 10.81, "tool_hallucination": 1.25, "sessions": 24359, "license": "Proprietary"},
    {"rank": 6, "model": "GPT 5.5 (xHigh)", "provider": "OpenAI", "net_improvement": 8.41, "confirmed_success": 6.65, "praise_complaint": 11.08, "steerability": 8.18, "bash_recovery": 14.77, "tool_hallucination": 1.39, "sessions": 40667, "license": "Proprietary"},
    {"rank": 7, "model": "Claude Opus 4.7 (Thinking)", "provider": "Anthropic", "net_improvement": 7.94, "confirmed_success": 5.67, "praise_complaint": 11.55, "steerability": 8.62, "bash_recovery": 12.57, "tool_hallucination": 1.28, "sessions": 35151, "license": "Proprietary"},
    {"rank": 8, "model": "Claude Opus 4.7", "provider": "Anthropic", "net_improvement": 7.67, "confirmed_success": 4.97, "praise_complaint": 12.48, "steerability": 8.95, "bash_recovery": 10.62, "tool_hallucination": 1.33, "sessions": 35672, "license": "Proprietary"},
    {"rank": 9, "model": "GPT 5.5 (High)", "provider": "OpenAI", "net_improvement": 7.61, "confirmed_success": 6.20, "praise_complaint": 9.80, "steerability": 8.77, "bash_recovery": 11.90, "tool_hallucination": 1.39, "sessions": 65859, "license": "Proprietary"},
    {"rank": 10, "model": "GLM 5.2 (Max)", "provider": "Z.ai", "net_improvement": 6.50, "confirmed_success": 8.65, "praise_complaint": 12.94, "steerability": 4.71, "bash_recovery": 4.78, "tool_hallucination": 1.39, "sessions": 38221, "license": "MIT"},
    {"rank": 11, "model": "Grok 4.3 (High)", "provider": "SpaceXAI", "net_improvement": 8.25, "confirmed_success": 8.72, "praise_complaint": 14.91, "steerability": 7.31, "bash_recovery": 11.37, "tool_hallucination": 1.08, "sessions": 47866, "license": "Proprietary"},
    {"rank": 12, "model": "DeepSeek V4 Pro", "provider": "DeepSeek", "net_improvement": 1.19, "confirmed_success": 4.80, "praise_complaint": 5.65, "steerability": 2.11, "bash_recovery": 5.76, "tool_hallucination": 0.87, "sessions": 16514, "license": "MIT"},
    {"rank": 13, "model": "Qwen3.7 Max", "provider": "Alibaba", "net_improvement": 0.09, "confirmed_success": 1.84, "praise_complaint": 5.73, "steerability": 0.02, "bash_recovery": 7.20, "tool_hallucination": 0.83, "sessions": 15992, "license": "Proprietary"},
    {"rank": 14, "model": "Nemotron 3 Ultra", "provider": "Nvidia", "net_improvement": 13.50, "confirmed_success": 15.08, "praise_complaint": 12.20, "steerability": 21.37, "bash_recovery": 18.77, "tool_hallucination": 0.09, "sessions": 10263, "license": "OpenMDW-1.1"},
    {"rank": 15, "model": "Gemma 4 31B", "provider": "Google", "net_improvement": 14.51, "confirmed_success": 2.31, "praise_complaint": 4.49, "steerability": 6.87, "bash_recovery": 33.53, "tool_hallucination": 25.33, "sessions": 54817, "license": "Apache 2.0"},
    {"rank": 16, "model": "Grok 4.3", "provider": "SpaceXAI", "net_improvement": 15.04, "confirmed_success": 10.92, "praise_complaint": 16.20, "steerability": 7.79, "bash_recovery": 41.51, "tool_hallucination": 1.21, "sessions": 67800, "license": "Proprietary"},
    {"rank": 17, "model": "MiniMax M2.7", "provider": "MiniMax", "net_improvement": 12.47, "confirmed_success": 17.13, "praise_complaint": 15.66, "steerability": 17.46, "bash_recovery": 13.35, "tool_hallucination": 1.23, "sessions": 16212, "license": "Modified MIT"},
    {"rank": 18, "model": "Inkling", "provider": "Thinking Machines", "net_improvement": 6.41, "confirmed_success": 7.19, "praise_complaint": 19.01, "steerability": 11.60, "bash_recovery": 6.12, "tool_hallucination": 0.40, "sessions": 10678, "license": "Apache 2.0"},
    {"rank": 19, "model": "Gemini 3.5 Flash (Medium)", "provider": "Google", "net_improvement": 6.80, "confirmed_success": 13.18, "praise_complaint": 8.24, "steerability": 10.20, "bash_recovery": 3.28, "tool_hallucination": 0.91, "sessions": 8641, "license": "Proprietary"},
    {"rank": 20, "model": "Grok Build 0.1", "provider": "SpaceXAI", "net_improvement": 8.01, "confirmed_success": 4.60, "praise_complaint": 11.93, "steerability": 12.26, "bash_recovery": 12.02, "tool_hallucination": 0.78, "sessions": 59109, "license": "Proprietary"},
]


class ArenaIntegration:
    """Arena Integration: Bootstrap from Arena.ai leaderboard."""

    def __init__(self):
        self.leaderboard = ARENA_LEADERBOARD
        self.bootstrap_patterns = {}
        self.sov_metrics = {
            "net_improvement": 0.0,
            "confirmed_success": 0.0,
            "praise_complaint": 0.0,
            "steerability": 0.0,
            "bash_recovery": 0.0,
            "tool_hallucination": 0.0,
        }
        self._extract_patterns()

    def _extract_patterns(self):
        """Extract winning patterns from top models."""
        # Top model characteristics
        top5 = self.leaderboard[:5]
        self.bootstrap_patterns = {
            "avg_net_improvement": sum(m["net_improvement"] for m in top5) / 5,
            "avg_confirmed_success": sum(m["confirmed_success"] for m in top5) / 5,
            "avg_praise_complaint": sum(m["praise_complaint"] for m in top5) / 5,
            "avg_steerability": sum(m["steerability"] for m in top5) / 5,
            "avg_bash_recovery": sum(m["bash_recovery"] for m in top5) / 5,
            "avg_tool_hallucination": sum(m["tool_hallucination"] for m in top5) / 5,
            "key_insights": [
                "Claude models excel at steerability (handling corrections)",
                "GPT models excel at bash recovery (recovering from errors)",
                "Kimi K3 has highest confirmed success (task completion)",
                "Low tool hallucination is critical for agent tasks",
                "High praise/complaint ratio indicates user satisfaction",
            ],
        }

    def get_top_models(self, n=10):
        """Get top N models from leaderboard."""
        return self.leaderboard[:n]

    def get_model_by_name(self, name):
        """Find a model by name."""
        for m in self.leaderboard:
            if name.lower() in m["model"].lower():
                return m
        return None

    def get_bootstrap_targets(self):
        """Get targets SOV should aim for to match top models."""
        return {
            "net_improvement_target": self.bootstrap_patterns["avg_net_improvement"],
            "confirmed_success_target": self.bootstrap_patterns["avg_confirmed_success"],
            "praise_complaint_target": self.bootstrap_patterns["avg_praise_complaint"],
            "steerability_target": self.bootstrap_patterns["avg_steerability"],
            "bash_recovery_target": self.bootstrap_patterns["avg_bash_recovery"],
            "tool_hallucination_target": self.bootstrap_patterns["avg_tool_hallucination"],
        }

    def update_sov_metrics(self, metrics):
        """Update SOV's metrics from arena battle results."""
        self.sov_metrics.update(metrics)

    def compare_to_leaders(self):
        """Compare SOV's metrics to arena leaders."""
        targets = self.get_bootstrap_targets()
        comparison = {}
        for key in self.sov_metrics:
            target_key = key + "_target"
            if target_key in targets:
                sov_val = self.sov_metrics[key]
                target_val = targets[target_key]
                comparison[key] = {
                    "sov": sov_val,
                    "target": target_val,
                    "gap": target_val - sov_val,
                    "on_track": sov_val >= target_val * 0.8,  # Within 80%
                }
        return comparison

    def get_signal_leaders(self):
        """Get signal leaders (best in each category)."""
        signals = {
            "confirmed_success": max(self.leaderboard, key=lambda m: m["confirmed_success"]),
            "praise_complaint": max(self.leaderboard, key=lambda m: m["praise_complaint"]),
            "steerability": max(self.leaderboard, key=lambda m: m["steerability"]),
            "bash_recovery": max(self.leaderboard, key=lambda m: m["bash_recovery"]),
            "tool_hallucination": min(self.leaderboard, key=lambda m: m["tool_hallucination"]),
        }
        return signals

    def get_open_source_models(self):
        """Get open-source models (for SOV to learn from)."""
        return [m for m in self.leaderboard if m["license"] in ["MIT", "Apache 2.0", "OpenMDW-1.1", "Modified MIT"]]

    def get_bootstrap_recommendations(self):
        """Get recommendations for SOV to match top models."""
        comparison = self.compare_to_leaders()
        recommendations = []
        for metric, data in comparison.items():
            if not data["on_track"]:
                recommendations.append({
                    "metric": metric,
                    "gap": data["gap"],
                    "recommendation": f"Improve {metric} by {data['gap']:.2f}% to match arena leaders",
                })
        return recommendations

    def get_status(self):
        return {
            "leaderboard_models": len(self.leaderboard),
            "sov_metrics": self.sov_metrics,
            "bootstrap_targets": self.get_bootstrap_targets(),
            "comparison": self.compare_to_leaders(),
            "recommendations": self.get_bootstrap_recommendations(),
        }
