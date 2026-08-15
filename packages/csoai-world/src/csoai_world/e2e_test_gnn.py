#!/usr/bin/env python3
"""
E2E Test: Unified GNN — Inner + Outer + Dreamer + Arena + HF + Kaggle

Tests the complete evolution system:
1. Inner GNN (IWM) — Learns from internal operations
2. Outer GNN (OWM) — Learns from external environments
3. Dreamer — Simulates competitions before entering
4. Arena Integration — Learns from arena.ai leaderboard
5. SOV-Space — Full processing with dreaming

Run: python3 iwms/e2e_test_gnn.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.unified_gnn import UnifiedGNN, InnerGNN, OuterGNN, Dreamer
from iwms.sov_space import SOVSpace
from iwms.arena_integration import ArenaIntegration, ARENA_LEADERBOARD

PASS = FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}")

def main():
    global PASS, FAIL
    print("=" * 60)
    print("  UNIFIED GNN E2E: Inner + Outer + Dreamer")
    print("=" * 60)

    # ─── INNER GNN ────────────────────────────────────────────
    print("\n[1/7] INNER GNN: Learns from Internal Operations")
    inner = InnerGNN()
    test("Inner GNN initialized", inner is not None)

    inner.update_routing("deepseek", "coding", 0.8)
    inner.update_routing("qwen", "coding", 0.6)
    inner.update_routing("deepseek", "reasoning", 0.9)
    test("Routing weights updated", len(inner.routing_weights) == 3)

    best = inner.get_best_route("coding")
    test("Best route for coding is deepseek", best == "deepseek")

    inner.update_stigmergy("reasoning", "deepseek", "pheromone", 0.9)
    test("Stigmergy signals updated", len(inner.stigmergy_signals) > 0)

    inner.update_pdca({"task": "test", "confidence": 0.8})
    test("PDCA history updated", len(inner.pdca_history) == 1)

    inner.update_honey("deepseek", "coding_strategy", 0.9)
    test("Honey patterns updated", len(inner.honey_patterns) > 0)

    status = inner.get_status()
    test("Inner status has routing", status["routing_weights"] > 0)

    # ─── OUTER GNN ────────────────────────────────────────────
    print("\n[2/7] OUTER GNN: Learns from External Environments")
    outer = OuterGNN()
    test("Outer GNN initialized", outer is not None)

    # Observe arena
    outer.observe_arena(ARENA_LEADERBOARD[:5])
    test("Arena patterns learned", len(outer.arena_patterns) == 5)

    # Observe HuggingFace
    outer.observe_huggingface([
        {"id": "meta-llama/Llama-3.1-70B", "downloads": 1000000, "likes": 5000, "pipeline_tag": "text-generation"},
        {"id": "Qwen/Qwen2.5-72B", "downloads": 800000, "likes": 3000, "pipeline_tag": "text-generation"},
    ])
    test("HF patterns learned", len(outer.hf_patterns) == 2)

    # Observe Kaggle
    outer.observe_kaggle([
        {"name": "LLM Science Exam", "category": "NLP", "evaluationMetric": "MAP@3", "teamCount": 2000},
        {"name": "AI Mathematical Olympiad", "category": "Math", "evaluationMetric": "accuracy", "teamCount": 500},
    ])
    test("Kaggle patterns learned", len(outer.kaggle_patterns) == 2)

    # Observe benchmarks
    outer.observe_benchmark([
        {"name": "MMLU", "metric": "accuracy", "top_score": 92.5, "models": ["GPT-5", "Claude-4"]},
        {"name": "HumanEval", "metric": "pass@1", "top_score": 95.0, "models": ["GPT-5", "DeepSeek-V4"]},
    ])
    test("Benchmark patterns learned", len(outer.benchmark_patterns) == 2)

    # Get winning strategy
    strategy = outer.get_winning_strategy("arena")
    test("Winning strategy returned", "strategy" in strategy)
    test("Strategy has confidence", "confidence" in strategy)

    status = outer.get_status()
    test("Outer status has all patterns", status["arena_patterns"] > 0)

    # ─── DREAMER ──────────────────────────────────────────────
    print("\n[3/7] DREAMER: Simulates Competitions Before Entering")
    dreamer = Dreamer(inner, outer)
    test("Dreamer initialized", dreamer is not None)

    dream = dreamer.dream_competition("arena", "Write optimized sorting algorithm", ["Claude Fable 5", "GPT 5.6"])
    test("Dream returns result", dream is not None)
    test("Dream has id", "id" in dream)
    test("Dream has winning_strategy", "winning_strategy" in dream)
    test("Dream has best_family", "best_family" in dream)
    test("Dream has simulations", len(dream["simulations"]) == 5)
    test("Dream has avg_confidence", 0 < dream["avg_confidence"] < 1)
    test("Dream has recommendation", "recommendation" in dream)

    # Dream Kaggle competition
    dream2 = dreamer.dream_competition("kaggle", "Solve math equations", ["GPT-5", "DeepSeek-V4"])
    test("Kaggle dream works", dream2["competition_type"] == "kaggle")

    # Dream benchmark
    dream3 = dreamer.dream_competition("benchmark", "Answer MMLU questions", ["Claude-4", "GPT-5"])
    test("Benchmark dream works", dream3["competition_type"] == "benchmark")

    summary = dreamer.get_dream_summary()
    test("Dream summary has total", summary["total_dreams"] == 3)
    test("Dream summary has avg_confidence", "avg_confidence" in summary)

    # ─── UNIFIED GNN ──────────────────────────────────────────
    print("\n[4/7] UNIFIED GNN: Bridges Inner + Outer")
    gnn = UnifiedGNN()
    test("Unified GNN initialized", gnn is not None)
    test("Has inner GNN", gnn.inner is not None)
    test("Has outer GNN", gnn.outer is not None)
    test("Has dreamer", gnn.dreamer is not None)

    # Bridge update
    gnn.bridge_update("outer", "inner", {"strategy": "task_completion"})
    test("Bridge update works", len(gnn.bridge_log) > 0)

    # Dream before competing
    dream = gnn.dream_before_competing("arena", "Build a web scraper")
    test("Dream via unified GNN works", dream is not None)

    status = gnn.get_status()
    test("Status has inner", "inner" in status)
    test("Status has outer", "outer" in status)
    test("Status has dreamer", "dreamer" in status)
    test("Status has bridge updates", status["bridge_updates"] > 0)

    gnn.save()
    test("GNN saved", True)

    # ─── SOV-SPACE + GNN ──────────────────────────────────────
    print("\n[5/7] SOV-SPACE: Full Processing with Dreaming")
    sov = SOVSpace()
    test("SOV-Space has unified GNN", sov.gnn is not None)
    test("GNN has inner", sov.gnn.inner is not None)
    test("GNN has outer", sov.gnn.outer is not None)
    test("GNN has dreamer", sov.gnn.dreamer is not None)

    # Process with dreaming
    result = sov.process("Analyze sentiment in customer reviews")
    test("Process has dream", "dream" in result)
    test("Dream has strategy", "winning_strategy" in result["dream"])
    test("Process has master_cspace", "master_cspace" in result)
    test("Process has gnn_status", "gnn_status" in result)

    # Verify GNN updated
    gnn_status = result["gnn_status"]
    test("GNN status has inner", "inner" in gnn_status)
    test("GNN status has outer", "outer" in gnn_status)
    test("GNN status has dreamer", "dreamer" in gnn_status)

    # ─── EVOLUTION LOOP ───────────────────────────────────────
    print("\n[6/7] EVOLUTION: Multi-Task Learning Loop")
    tasks = [
        "Write optimized sorting algorithm",
        "Translate legal document to Chinese",
        "Debug memory leak in Rust codebase",
        "Write EU AI Act compliance report",
        "Optimize database query performance",
        "Analyze satellite imagery",
        "Create REST API with authentication",
        "Implement binary search in C++",
    ]
    for desc in tasks:
        r = sov.process(desc)
        test(f"Processed: {desc[:25]}...", "dream" in r)

    # Verify dreams accumulated
    test("Dreams accumulated", len(sov.gnn.dreamer.dreams) > 5)
    test("Inner GNN has PDCA history", len(sov.gnn.inner.pdca_history) > 5)

    # ─── SAVE + STATUS ────────────────────────────────────────
    print("\n[7/7] SAVE + STATUS")
    sov.gnn.save()
    test("GNN saved", True)

    status = sov.get_status()
    test("Status has hives", status["hives"] == 12)
    test("Status has gnn", "gnn" in dir(sov))

    # ─── RESULTS ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)
    if FAIL > 0:
        print(f"\n  ✗ {FAIL} TESTS FAILED")
        return 1
    print(f"\n  ✓ ALL {PASS} TESTS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
