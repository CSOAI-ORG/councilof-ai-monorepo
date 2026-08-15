"""eu_ai_act_mcp — SCAFFOLD server (v0.1.0).

Honest minimal scaffold. Replace with real source when migrated.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

# Static table: 13 EU AI Act articles + Annex III high-risk categories
# + cross-reference to NIST AI RMF functions.
ARTICLES = [
    {"id": "Art5", "title": "Prohibited Practices",
     "summary": "AI systems that deploy subliminal manipulation, exploit vulnerabilities of specific groups, are used for social scoring by public authorities, or perform real-time remote biometric identification in publicly accessible spaces for law enforcement (with limited exceptions) are prohibited.",
     "nist_rmf": "GOVERN-1.1",
     "iso_42001": "Clause 5.2"},
    {"id": "Art9", "title": "Risk Management",
     "summary": "High-risk AI systems must implement a continuous risk-management process across the lifecycle.",
     "nist_rmf": "MANAGE-2.2",
     "iso_42001": "Clause 6.1.2"},
    {"id": "Art10", "title": "Data Governance",
     "summary": "Training/validation/test datasets must be relevant, representative, free of errors, and complete.",
     "nist_rmf": "MAP-2.1",
     "iso_42001": "Clause 8.5"},
    {"id": "Art11", "title": "Technical Documentation",
     "summary": "Providers must draw up and maintain technical documentation before market placement.",
     "nist_rmf": "GOVERN-2.1",
     "iso_42001": "Clause 7.5"},
    {"id": "Art12", "title": "Record-Keeping",
     "summary": "High-risk AI systems must have automatic logging of events throughout the lifecycle.",
     "nist_rmf": "MANAGE-4.1",
     "iso_42001": "Clause 8.4"},
    {"id": "Art13", "title": "Transparency",
     "summary": "High-risk AI systems must be designed to allow interpretability and explainability.",
     "nist_rmf": "EXPLAIN-1.1",
     "iso_42001": "Clause 8.6"},
    {"id": "Art14", "title": "Human Oversight",
     "summary": "High-risk AI systems must enable effective human oversight during use.",
     "nist_rmf": "GOVERN-2.2",
     "iso_42001": "Clause 8.7"},
    {"id": "Art15", "title": "Accuracy, Robustness, Cybersecurity",
     "summary": "High-risk AI systems must be accurate, robust, and protected against cybersecurity threats.",
     "nist_rmf": "MANAGE-2.3",
     "iso_42001": "Clause 8.8"},
    {"id": "Art17", "title": "Quality Management System",
     "summary": "Providers of high-risk AI must implement a QMS ensuring compliance.",
     "nist_rmf": "GOVERN-3.1",
     "iso_42001": "Clause 7.1"},
    {"id": "Art26", "title": "Deployer Obligations",
     "summary": "Deployers of high-risk AI must use systems per instructions, monitor, and inform providers of serious risks.",
     "nist_rmf": "MANAGE-1.3",
     "iso_42001": "Clause 8.8"},
    {"id": "Art50", "title": "Transparency for AI Interacting with People",
     "summary": "Providers of AI systems intended to interact directly with natural persons must disclose they are interacting with an AI system.",
     "nist_rmf": "GOVERN-1.5",
     "iso_42001": "Clause 8.6"},
    {"id": "Art51", "title": "Classification Rules for General-Purpose AI",
     "summary": "GPAI models must be classified by computational thresholds and systemic risk.",
     "nist_rmf": "GOVERN-2.3",
     "iso_42001": "Clause 8.9"},
    {"id": "AnnexIII", "title": "High-Risk AI Use Cases",
     "summary": "Biometric ID, critical infrastructure, education, employment, essential services, law enforcement, migration, justice, democratic processes.",
     "nist_rmf": "GOVERN-2.1",
     "iso_42001": "Clause 5.3"},
]


def eu_ai_act_query(query: str) -> List[Dict[str, Any]]:
    """Search EU AI Act articles matching the query string (case-insensitive)."""
    if not query or not query.strip():
        return []
    q = query.lower()
    results = []
    for art in ARTICLES:
        haystack = (art["id"] + " " + art["title"] + " " + art["summary"]).lower()
        if q in haystack or any(token in haystack for token in q.split() if len(token) > 3):
            results.append({
                "id": art["id"],
                "title": art["title"],
                "summary": art["summary"],
                "nist_rmf": art["nist_rmf"],
                "iso_42001": art["iso_42001"],
            })
    return results


def main() -> None:
    """Entry point for `python -m eu_ai_act_mcp`."""
    print("eu-ai-act-mcp SCAFFOLD v0.1.0")
    print(f"Loaded {len(ARTICLES)} articles")
    # Demo
    for q in ["Article 5 prohibited", "transparency", "human oversight"]:
        results = eu_ai_act_query(q)
        print(f"  '{q}' → {len(results)} matches")


if __name__ == "__main__":
    main()


__all__ = ["eu_ai_act_query", "ARTICLES", "main"]