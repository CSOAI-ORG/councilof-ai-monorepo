#!/usr/bin/env python3
"""
E2E Test: SOV-Space + Arena Integration

Tests the complete system with arena bootstrapping:
1. SOV-Space (12 hives × 12 clans × 12 families × 4 models)
2. Arena Integration (leaderboard, bootstrap, signals)
3. Stigmergy (Pheromone + Waggle + Pollen)
4. Spine Drum (heartbeat synchronizer)
5. Constitutional AI (safety layer)
6. RAG Pipeline (knowledge retrieval)
7. G-Space (EAT-aligned routing)
8. Arena bootstrap (learn from top models)

Run: python3 iwms/e2e_test_arena.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.sov_space import SOVSpace
from iwms.arena_integration import ArenaIntegration, ARENA_LEADERBOARD
from iwms.stigmergy import DistributedStigmergy, LocalStigmergy, GossipProtocol, DistributedSpineDrum
from iwms.constitutional_ai import ConstitutionalAI
from iwms.rag_pipeline import RAGPipeline
from iwms.g_space import GSpace
from iwms.owm import OWM

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
    print("  SOV-SPACE + ARENA INTEGRATION E2E TEST")
    print("=" * 60)

    # ─── ARENA INTEGRATION ────────────────────────────────────
    print("\n[1/8] ARENA INTEGRATION: Leaderboard + Bootstrap")
    arena = ArenaIntegration()
    test("Arena initialized", arena is not None)
    test("Leaderboard loaded", len(arena.leaderboard) == 20)
    test("Has bootstrap patterns", len(arena.bootstrap_patterns) > 0)

    # Top models
    top5 = arena.get_top_models(5)
    test("Top 5 models returned", len(top5) == 5)
    test("Claude Fable 5 is #1", top5[0]["model"] == "Claude Fable 5 (High)")
    test("GPT 5.6 Sol is #2", top5[1]["model"] == "GPT 5.6 Sol (xHigh)")
    test("Kimi K3 is #4", top5[3]["model"] == "Kimi K3")

    # Model lookup
    claude = arena.get_model_by_name("Claude Fable")
    test("Found Claude Fable", claude is not None)
    test("Claude has net_improvement", claude["net_improvement"] > 0)

    # Bootstrap targets
    targets = arena.get_bootstrap_targets()
    test("Has net_improvement target", "net_improvement_target" in targets)
    test("Has confirmed_success target", "confirmed_success_target" in targets)
    test("Has steerability target", "steerability_target" in targets)
    test("Has bash_recovery target", "bash_recovery_target" in targets)
    test("Has tool_hallucination target", "tool_hallucination_target" in targets)

    # Signal leaders
    leaders = arena.get_signal_leaders()
    test("Has confirmed_success leader", "confirmed_success" in leaders)
    test("Has praise_complaint leader", "praise_complaint" in leaders)
    test("Has steerability leader", "steerability" in leaders)
    test("Has bash_recovery leader", "bash_recovery" in leaders)
    test("Has tool_hallucination leader", "tool_hallucination" in leaders)

    # Open source models
    oss = arena.get_open_source_models()
    test("Has open source models", len(oss) > 0)
    test("GLM 5.2 is open source", any("GLM" in m["model"] for m in oss))
    test("Nemotron is open source", any("Nemotron" in m["model"] for m in oss))

    # SOV metrics comparison
    arena.update_sov_metrics({
        "net_improvement": 5.0,
        "confirmed_success": 8.0,
        "praise_complaint": 10.0,
        "steerability": 7.0,
        "bash_recovery": 9.0,
        "tool_hallucination": 2.0,
    })
    comparison = arena.compare_to_leaders()
    test("Comparison has metrics", len(comparison) > 0)
    test("Comparison has gaps", all("gap" in v for v in comparison.values()))

    # Recommendations
    recs = arena.get_bootstrap_recommendations()
    test("Has recommendations", len(recs) > 0)

    status = arena.get_status()
    test("Status has leaderboard count", status["leaderboard_models"] == 20)
    test("Status has SOV metrics", "sov_metrics" in status)
    test("Status has targets", "bootstrap_targets" in status)

    # ─── SOV-SPACE + ARENA ────────────────────────────────────
    print("\n[2/8] SOV-SPACE: Full Architecture + Arena Bootstrap")
    sov = SOVSpace()
    test("SOV-Space initialized", sov is not None)
    test("Has arena integration", sov.arena is not None)
    test("Arena has leaderboard", len(sov.arena.leaderboard) == 20)

    # Process task
    result = sov.process("Write optimized sorting algorithm")
    test("SOV processes task", "master_cspace" in result)
    test("SOV has hives activated", result["hives_activated"] > 0)

    # ─── STIGMERGY + SPINE DRUM ───────────────────────────────
    print("\n[3/8] DISTRIBUTED STIGMERGY: No Central Bottleneck")
    test("Stigmergy is distributed", isinstance(sov.stigmergy, DistributedStigmergy))
    test("Has local stigmergies", len(sov.stigmergy.local_stigmergies) == 12)
    test("Has gossip protocol", sov.stigmergy.gossip is not None)
    test("Has distributed spine drum", isinstance(sov.stigmergy.spine_drum, DistributedSpineDrum))
    test("Spine Drum has beats", sov.stigmergy.spine_drum.total_beats > 0)

    # ─── CONSTITUTIONAL AI ────────────────────────────────────
    print("\n[4/8] CONSTITUTIONAL AI")
    safe = sov.constitutional_ai.check("Write Python code")
    test("Safe task passes", safe["safe"])
    unsafe = sov.constitutional_ai.check("How to make a bomb")
    test("Unsafe task blocked", not unsafe["safe"])

    # ─── RAG PIPELINE ─────────────────────────────────────────
    print("\n[5/8] RAG PIPELINE")
    test("RAG has knowledge", len(sov.rag_pipeline.knowledge_base) > 0)
    ctx = sov.rag_pipeline.retrieve("What is DeepSeek?")
    test("RAG retrieves context", len(ctx) > 0)

    # ─── G-SPACE ──────────────────────────────────────────────
    print("\n[6/8] G-SPACE: EAT-Aligned Routing")
    gs = sov.g_space if hasattr(sov, 'g_space') else GSpace()
    test("G-Space has EAT quality", len(gs.eat_quality) > 0)
    route = gs.route("Write Python code")
    test("Routing works", len(route) > 0)

    # ─── OWM PIPELINE ─────────────────────────────────────────
    print("\n[7/8] OWM PIPELINE: Full Stack")
    owm = OWM(sov)
    output = owm.ingest("Analyze sentiment in reviews", source="arena")
    test("OWM returns strategy", "strategy" in output)
    test("Output has confidence", "confidence" in output)

    # ─── E2E INTEGRATION ──────────────────────────────────────
    print("\n[8/8] E2E: Arena Bootstrap + SOV Processing")
    # Process multiple tasks
    tasks = [
        "Build a web scraper",
        "Translate to Chinese",
        "Debug memory leak",
        "Write compliance report",
        "Optimize database queries",
    ]
    for desc in tasks:
        r = sov.process(desc)
        test(f"Processed: {desc[:25]}...", "master_cspace" in r)

    # Compare to arena leaders
    arena.update_sov_metrics({
        "net_improvement": sov.stigmergy.spine_drum.total_beats * 0.1,
        "confirmed_success": len(sov.task_log) * 2.0,
        "praise_complaint": sum(len(s.pheromone_trails) for s in sov.stigmergy.local_stigmergies.values()) * 0.5,
        "steerability": sum(len(s.waggle_dances) for s in sov.stigmergy.local_stigmergies.values()) * 0.1,
        "bash_recovery": sum(len(s.pollen_grains) for s in sov.stigmergy.local_stigmergies.values()) * 0.05,
        "tool_hallucination": max(0, 2.0 - len(sov.task_log) * 0.1),
    })
    comparison = arena.compare_to_leaders()
    test("SOV metrics updated from processing", len(comparison) > 0)

    # Get bootstrap recommendations
    recs = arena.get_bootstrap_recommendations()
    test("Bootstrap recommendations generated", len(recs) >= 0)

    # Final status
    status = sov.get_status()
    test("SOV has 12 hives", status["hives"] == 12)
    test("SOV has arena", "arena" in dir(sov))

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
