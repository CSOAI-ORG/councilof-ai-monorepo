"""
OWM: Outer World Model

The OWM is the external interface to SOV space. It:
1. Receives tasks from the outside world (Kaggle, benchmarks, APIs)
2. Scans competitors to identify their model type
3. Passes tasks into IWM for PDCA processing
4. Formats and delivers SOV's strategy output
5. Receives outcomes and feeds back into IWM for learning

OWM never directly touches internal clans — it talks to IWM only.
"""
import json, re
from pathlib import Path
from datetime import datetime

IWM_DIR = Path(__file__).resolve().parent

COMPETITOR_SIGNATURES = {
    "gpt-4": {"family": "openai", "strengths": ["reasoning", "coding", "tool_use"], "weaknesses": ["cost", "speed"]},
    "gpt-4o": {"family": "openai", "strengths": ["multimodal", "speed"], "weaknesses": ["cost"]},
    "claude": {"family": "anthropic", "strengths": ["reasoning", "safety", "writing"], "weaknesses": ["vision", "tool_use"]},
    "gemini": {"family": "google", "strengths": ["multimodal", "context_length"], "weaknesses": ["safety", "consistency"]},
    "copilot": {"family": "microsoft", "strengths": ["coding", "ide_integration"], "weaknesses": ["reasoning", "multilingual"]},
    "llama": {"family": "meta", "strengths": ["open_source", "community"], "weaknesses": ["safety", "instruction_following"]},
    "mistral": {"family": "mistral", "strengths": ["speed", "multilingual"], "weaknesses": ["vision", "context_length"]},
    "qwen": {"family": "alibaba", "strengths": ["multilingual", "coding"], "weaknesses": ["safety"]},
    "deepseek": {"family": "deepseek", "strengths": ["reasoning", "math", "coding"], "weaknesses": ["speed"]},
    "nemotron": {"family": "nvidia", "strengths": ["hardware_optimization", "synthetic_data"], "weaknesses": ["community"]},
}


class OWM:
    """Outer World Model: external interface to SOV space."""

    def __init__(self, iwm=None):
        from .iwm import IWM
        self.iwm = iwm or IWM()
        self.ingest_log = []

    def ingest(self, task, source="external", competitor_hint=None):
        """
        Ingest a task from the outer world.
        
        Args:
            task: dict with keys: description, type, context, constraints
                  or just a string description
            source: where the task came from (kaggle, benchmark, api, user)
            competitor_hint: optional hint about the competitor model
        
        Returns:
            SOV's unified strategy output
        """
        if isinstance(task, str):
            task = {"description": task, "type": "general", "source": source}
        # Scan for competitor if not provided
        competitor = competitor_hint or self._scan_competitor(task)
        task["competitor"] = competitor
        task["ingested_at"] = datetime.now().isoformat()
        self.ingest_log.append(task)
        # Pass to IWM for PDCA processing
        result = self.iwm.run_pdca(task)
        # Format output for outer world
        output = self._format_output(result, task)
        return output

    def _scan_competitor(self, task):
        """Scan task description for competitor signatures."""
        desc = task.get("description", "").lower()
        for name, sig in COMPETITOR_SIGNATURES.items():
            if name in desc:
                return {"name": name, **sig}
        # Check context
        context = task.get("context", "").lower()
        for name, sig in COMPETITOR_SIGNATURES.items():
            if name in context:
                return {"name": name, **sig}
        return {"name": "unknown", "family": "unknown", "strengths": [], "weaknesses": []}

    def _format_output(self, pdca_result, task):
        """Format IWM result for external consumption."""
        return {
            "strategy": pdca_result["strategy"],
            "confidence": pdca_result["confidence"],
            "clan_alliance": pdca_result["alliance"],
            "pdca_cycle": pdca_result["cycle"],
            "competitor_analysis": task.get("competitor", {}),
            "recommendations": pdca_result.get("recommendations", []),
            "source": "sov_space",
            "timestamp": datetime.now().isoformat(),
        }

    def receive_outcome(self, task_id, won, details=None):
        """Receive outcome from the outer world and feed into IWM."""
        # Find the task in ingest log
        task = None
        for t in self.ingest_log:
            if t.get("ingested_at") == task_id or t.get("description", "")[:50] == task_id[:50]:
                task = t
                break
        if task:
            self.iwm.receive_outcome(task, won, details)
        return {"acknowledged": True, "task_found": task is not None}

    def get_external_status(self):
        """Get OWM status for external monitoring."""
        return {
            "tasks_ingested": len(self.ingest_log),
            "iwm_status": self.iwm.get_status(),
            "known_competitors": list(COMPETITOR_SIGNATURES.keys()),
        }
