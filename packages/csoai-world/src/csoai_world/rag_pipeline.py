"""
RAG PIPELINE: Knowledge Retrieval

Retrieves relevant knowledge from EAT extraction data
before processing tasks through the hive.

Flow:
1. Query → Embed (simplified: keyword extraction)
2. Search EAT knowledge base
3. Retrieve top-K relevant entries
4. Inject as context into task processing
"""
import json, re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
EAT_DIR = ROOT / "eat_results"


class RAGPipeline:
    """RAG Pipeline: Knowledge retrieval from EAT data."""

    def __init__(self):
        self.knowledge_base = self._load_knowledge_base()
        self.query_count = 0

    def _load_knowledge_base(self):
        """Load all EAT knowledge into searchable index."""
        kb = []
        # Load from free_gpu_eat_all.json
        all_path = EAT_DIR / "free_gpu_eat_all.json"
        if all_path.exists():
            try:
                entries = json.loads(all_path.read_text())
                for entry in entries:
                    if entry.get("ok"):
                        kb.append({
                            "family": entry.get("family", "unknown"),
                            "question": entry.get("q", ""),
                            "answer": entry.get("a", ""),
                            "source": entry.get("source", "unknown"),
                            "tokens": set((entry.get("q", "") + " " + entry.get("a", "")).lower().split()),
                        })
            except Exception:
                pass
        # Load from per-family extract files
        for extract_file in EAT_DIR.glob("extract_*.json"):
            try:
                entries = json.loads(extract_file.read_text())
                for entry in entries:
                    if entry.get("a"):
                        kb.append({
                            "family": entry.get("family", extract_file.stem.replace("extract_", "")),
                            "question": entry.get("q", ""),
                            "answer": entry.get("a", ""),
                            "source": "extract_file",
                            "tokens": set((entry.get("q", "") + " " + entry.get("a", "")).lower().split()),
                        })
            except Exception:
                pass
        return kb

    def retrieve(self, query, top_k=5):
        """Retrieve relevant knowledge for a query."""
        self.query_count += 1
        if not self.knowledge_base:
            return ""
        if isinstance(query, dict):
            query = query.get("description", str(query))
        query_tokens = set(query.lower().split())

        # Score each entry by token overlap
        scored = []
        for entry in self.knowledge_base:
            overlap = len(query_tokens & entry["tokens"])
            if overlap > 0:
                scored.append((overlap, entry))

        # Sort by score
        scored.sort(key=lambda x: x[0], reverse=True)

        # Return top-K answers as context
        contexts = []
        for score, entry in scored[:top_k]:
            contexts.append(f"[{entry['family']}] Q: {entry['question']}\nA: {entry['answer'][:200]}")

        return "\n\n".join(contexts)

    def get_status(self):
        return {
            "knowledge_entries": len(self.knowledge_base),
            "queries": self.query_count,
        }
