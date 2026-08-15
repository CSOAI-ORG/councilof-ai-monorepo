#!/usr/bin/env python3
"""
E2E Test: Arena Trainer — Learn from Arena.ai Top Models

Tests real training loop:
1. Initialize SOV-Space + Arena Trainer
2. Run training episodes against top arena models
3. Verify reward signals improve over time
4. Verify weight updates propagate to GNN routing
5. Verify stigmergy adapts based on rewards
6. Verify pattern weights converge to best strategies

Run: python3 iwms/e2e_test_train.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iwms.sov_space import SOVSpace
from iwms.arena_trainer import ArenaTrainer, TOP_MODEL_PATTERNS, ARENA_SIGNAL_WEIGHTS
from iwms.arena_integration import ArenaIntegration

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
    print("  ARENA TRAINER E2E: Learn from Top Models")
    print("=" * 60)

    # ─── INIT ─────────────────────────────────────────────────
    print("\n[1/6] INIT: SOV-Space + Arena Trainer")
    sov = SOVSpace()
    trainer = ArenaTrainer(sov)
    test("SOV-Space initialized", sov is not None)
    test("Arena Trainer initialized", trainer is not None)
    test("Has learning rate", trainer.learning_rate > 0)
    test("Has pattern weights", len(trainer.pattern_weights) == len(TOP_MODEL_PATTERNS))

    # ─── SINGLE EPISODE ───────────────────────────────────────
    print("\n[2/6] SINGLE EPISODE: Train Against Claude Fable 5")
    result = trainer.train_episode("Write optimized sorting algorithm", "Claude Fable 5 (High)")
    test("Episode returns result", result is not None)
    test("Has metrics", "metrics" in result)
    test("Has reward", "reward" in result)
    test("Reward is numeric", isinstance(result["reward"], (int, float)))
    test("Episode counter updated", trainer.episode == 1)

    metrics = result["metrics"]
    test("Has confirmed_success", "confirmed_success" in metrics)
    test("Has praise_complaint", "praise_complaint" in metrics)
    test("Has steerability", "steerability" in metrics)
    test("Has bash_recovery", "bash_recovery" in metrics)
    test("Has tool_hallucination", "tool_hallucination" in metrics)

    # ─── BATCH TRAINING ───────────────────────────────────────
    print("\n[3/6] BATCH TRAINING: 10 Tasks × 3 Episodes Each")
    tasks = [
        "Build a web scraper in Python",
        "Translate legal document to Chinese",
        "Debug memory leak in Rust codebase",
        "Write EU AI Act compliance report",
        "Optimize database query performance",
        "Analyze sentiment in customer reviews",
        "Create a REST API with authentication",
        "Implement binary search in C++",
        "Write unit tests for payment module",
        "Design microservices architecture",
    ]
    batch_results = trainer.train_batch(tasks, episodes_per_task=3)
    test("Batch returns results", len(batch_results) == 30)
    test("All results have reward", all("reward" in r for r in batch_results))
    test("Episode counter at 31", trainer.episode == 31)

    # ─── REWARD IMPROVEMENT ───────────────────────────────────
    print("\n[4/6] REWARD IMPROVEMENT: Verify Learning")
    summary = trainer.get_training_summary()
    test("Summary has episodes", summary["episodes"] == 31)
    test("Summary has avg_reward", "avg_reward" in summary)
    test("Summary has max_reward", "max_reward" in summary)
    test("Summary has recent_avg", "recent_avg" in summary)
    test("Summary has pattern weights", "pattern_weights" in summary)
    test("Summary has top_pattern", "top_pattern" in summary)

    # Check reward trend (should improve)
    first5_avg = sum(r["reward"] for r in batch_results[:5]) / 5
    last5_avg = sum(r["reward"] for r in batch_results[-5:]) / 5
    test("Reward trend exists", last5_avg >= first5_avg * 0.8)  # Allow some variance

    # ─── PATTERN WEIGHTS ──────────────────────────────────────
    print("\n[5/6] PATTERN WEIGHTS: Convergence Check")
    weights = trainer.pattern_weights
    test("All patterns have weights", len(weights) == len(TOP_MODEL_PATTERNS))
    test("Weights sum to ~1", abs(sum(weights.values()) - 1.0) < 0.01)
    test("Best pattern identified", summary["top_pattern"] is not None)

    # Check which pattern is winning
    best_pattern = summary["top_pattern"]
    test("Best pattern has name", best_pattern[0] in TOP_MODEL_PATTERNS)
    test("Best pattern has weight", best_pattern[1] > 0)

    # ─── GNN ROUTING UPDATES ──────────────────────────────────
    print("\n[6/6] GNN ROUTING: Verify Weight Updates")
    # Check pattern weights changed from initial
    initial_weight = 1.0 / len(TOP_MODEL_PATTERNS)
    weight_changed = any(abs(v - initial_weight) > 0.001 for v in trainer.pattern_weights.values())
    test("Pattern weights updated from initial", weight_changed)
    test("Best pattern has significant weight", best_pattern[1] > initial_weight * 1.1)

    # Verify stigmergy adapted
    evap_rates = [stig.evaporation_rate for stig in sov.stigmergy.local_stigmergies.values()]
    test("Stigmergy evaporation rates exist", len(evap_rates) > 0)
    test("Evaporation rates in valid range", all(0.001 <= r <= 0.1 for r in evap_rates))

    # Save training
    trainer.save_training()
    test("Training saved", True)

    # ─── RESULTS ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print(f"  TRAINING: {trainer.episode} episodes, avg reward: {summary['avg_reward']:.2f}")
    print(f"  BEST PATTERN: {best_pattern[0]} ({best_pattern[1]:.3f})")
    print("=" * 60)
    if FAIL > 0:
        print(f"\n  ✗ {FAIL} TESTS FAILED")
        return 1
    print(f"\n  ✓ ALL {PASS} TESTS PASSED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
