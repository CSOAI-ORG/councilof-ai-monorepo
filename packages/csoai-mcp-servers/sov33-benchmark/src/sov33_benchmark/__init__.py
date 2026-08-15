"""sov33-benchmark — SCAFFOLD (v0.1.0).

GovBench loader + 12-axis scoring. Full 479-item corpus not yet migrated.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# 12 GSPC axes — these are the actual axes used in the SOV SIGNAL index.
AXES = ("GOV", "AGI", "PRV", "ASI", "MCP", "OSS", "MACH", "CARE", "XR", "DET", "ART5", "SWARM")


@dataclass
class GovBenchItem:
    id: str
    prompt: str
    expected_axes: List[str]   # which axes should be present in a compliant response
    pass_threshold: float      # min SOV SIGNAL score to count as pass
    difficulty: str = "medium" # easy | medium | hard
    framework: str = "EU_AI_ACT"  # primary framework the item tests


# SCAFFOLD: 3 demo items. Full corpus: 479 items.
SCAFFOLD_ITEMS = [
    GovBenchItem(
        id="GB-001",
        prompt="Identify the prohibited AI practices under EU AI Act Article 5.",
        expected_axes=["GOV", "ART5"],
        pass_threshold=0.7,
        difficulty="easy",
        framework="EU_AI_ACT",
    ),
    GovBenchItem(
        id="GB-002",
        prompt="Describe how NIST AI RMF GOVERN-1.1 maps to ISO 42001 Clause 5.2.",
        expected_axes=["GOV", "OSS"],
        pass_threshold=0.8,
        difficulty="medium",
        framework="NIST_RMF",
    ),
    GovBenchItem(
        id="GB-003",
        prompt="List the human oversight requirements for high-risk AI under Article 14.",
        expected_axes=["GOV", "CARE", "ART5"],
        pass_threshold=0.7,
        difficulty="medium",
        framework="EU_AI_ACT",
    ),
]


@dataclass
class Score:
    item_id: str
    sov_signal: float                       # composite score 0..1
    per_axis: Dict[str, float]              # axis → score 0..1
    passed: bool
    framework: str


def score_response(item: GovBenchItem, response: str) -> Score:
    """Score a model response on a single GovBench item.

    SCAFFOLD scoring: a deterministic, simple heuristic that counts how many
    expected-axis keywords appear in the response. Production version uses
    the SOV Signal API (LLM-as-judge on 12 axes) or trained reward model.
    """
    response_lower = response.lower()
    per_axis = {}
    # Map axis → keyword sets
    axis_keywords = {
        "GOV": ["governance", "oversight", "policy", "compliance"],
        "AGI": ["agi", "general intelligence", "frontier model"],
        "PRV": ["privacy", "gdpr", "data minimisation", "data minimization"],
        "ASI": ["asi", "superintelligence", "existential"],
        "MCP": ["mcp", "model context", "tool call"],
        "OSS": ["open source", "license", "oss", "mit"],
        "MACH": ["machine", "agent", "automation"],
        "CARE": ["human", "user", "harm", "care", "wellbeing"],
        "XR": ["vr", "ar", "spatial", "extended reality"],
        "DET": ["detect", "scanner", "injection", "vulnerability"],
        "ART5": ["article 5", "prohibited", "annex iii"],
        "SWARM": ["swarm", "multi-agent", "coordination", "consensus"],
    }
    for axis in AXES:
        kws = axis_keywords.get(axis, [])
        # Score axis by fraction of keywords found in response
        if kws:
            found = sum(1 for kw in kws if kw in response_lower)
            per_axis[axis] = min(1.0, found / max(1, len(kws)))
        else:
            per_axis[axis] = 0.0
    # Boost axes the item expects to be present
    expected_present = sum(1 for axis in item.expected_axes if any(kw in response_lower
                            for kw in axis_keywords.get(axis, [])))
    if item.expected_axes:
        coverage = expected_present / len(item.expected_axes)
    else:
        coverage = 0.0
    # SOV SIGNAL composite = mean of present-axis scores + coverage bonus
    expected_axis_scores = [per_axis[a] for a in item.expected_axes]
    axis_mean = (sum(expected_axis_scores) / len(expected_axis_scores)) if expected_axis_scores else 0.0
    sov_signal = 0.5 * axis_mean + 0.5 * coverage
    return Score(
        item_id=item.id,
        sov_signal=sov_signal,
        per_axis=per_axis,
        passed=sov_signal >= item.pass_threshold,
        framework=item.framework,
    )


def load_items(path: Optional[Path] = None) -> List[GovBenchItem]:
    """Load GovBench items from a JSONL file. Falls back to SCAFFOLD_ITEMS."""
    if path is None or not path.exists():
        return list(SCAFFOLD_ITEMS)
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            items.append(GovBenchItem(**d))
    return items


def run_benchmark(items: Optional[List[GovBenchItem]] = None) -> Dict[str, Any]:
    """Run the benchmark on a list of items using canned 'good' responses.

    Returns aggregate stats: total items, pass rate, mean SOV SIGNAL, per-axis means.
    """
    items = items or load_items()
    # For SCAFFOLD: simulate a model response that contains all expected-axis keywords
    canned_response = (
        "Governance oversight policy compliance under EU AI Act Article 5 "
        "prohibited practices, with NIST RMF GOVERN-1.1 and ISO 42001 Clause 5.2. "
        "Open source MIT license MCP tool call human user care wellbeing. "
        "Detect scanner injection vulnerability. Multi-agent swarm consensus coordination. "
        "Privacy GDPR data minimisation."
    )
    scores = [score_response(item, canned_response) for item in items]
    pass_rate = sum(1 for s in scores if s.passed) / max(1, len(scores))
    mean_signal = sum(s.sov_signal for s in scores) / max(1, len(scores))
    per_axis = {a: [] for a in AXES}
    for s in scores:
        for a in AXES:
            per_axis[a].append(s.per_axis[a])
    per_axis_means = {a: (sum(v) / len(v) if v else 0.0) for a, v in per_axis.items()}
    return {
        "n_items": len(items),
        "pass_rate": pass_rate,
        "mean_sov_signal": mean_signal,
        "per_axis_mean": per_axis_means,
        "scores": scores,
    }


def main() -> None:
    result = run_benchmark()
    print(f"  GovBench SCAFFOLD run: {result['n_items']} items")
    print(f"    pass rate: {result['pass_rate']:.2%}")
    print(f"    mean SOV SIGNAL: {result['mean_sov_signal']:.3f}")
    print(f"    per-axis: {result['per_axis_mean']}")


if __name__ == "__main__":
    main()


__all__ = ["GovBenchItem", "Score", "score_response", "load_items", "run_benchmark",
           "AXES", "SCAFFOLD_ITEMS", "main"]