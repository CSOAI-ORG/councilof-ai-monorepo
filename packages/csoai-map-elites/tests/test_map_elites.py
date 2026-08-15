"""Tests for csoai_map_elites — Hyperbolic MAP-Elites fitness gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_map_elites import (
    BALL_EPS, BALL_RADIUS, CARE_FLOOR, MUTATION_REJECT_THRESHOLD,
    HyperbolicMapElites, MutationVerdict,
    _default_fitness, _default_mutation,
    self_test,
)


def test_me01_project_to_ball_keeps_in_ball():
    """Vectors outside the ball get projected to the boundary."""
    me = HyperbolicMapElites(ball_radius=0.9)
    v = np.array([10.0, 0.0, 0.0, 0.0])  # norm = 10
    p = me.project_to_ball(v)
    assert np.linalg.norm(p) <= 0.9 + 1e-9
    assert np.linalg.norm(p) >= 0.89  # close to ball_radius
    print(f"  ✅ project_to_ball: norm 10 → {np.linalg.norm(p):.4f} (≤ {me.ball_radius})")


def test_me02_project_to_ball_keeps_short_vectors():
    """Vectors already inside the ball are unchanged."""
    me = HyperbolicMapElites(ball_radius=0.9)
    v = np.array([0.3, 0.1, -0.2, 0.05])
    p = me.project_to_ball(v)
    assert np.allclose(p, v), "short vector should be unchanged"
    print(f"  ✅ project_to_ball: short vector preserved")


def test_me03_behavior_to_cell_maps_to_grid():
    """Behavior coords map to integer cells in [0, grid_size-1]."""
    me = HyperbolicMapElites(grid_size=10, ball_radius=0.95)
    cell1 = me._behavior_to_cell(np.array([0.0, 0.0]))
    cell2 = me._behavior_to_cell(np.array([0.95, -0.95]))
    cell3 = me._behavior_to_cell(np.array([-0.95, 0.95]))
    for c in (cell1, cell2, cell3):
        assert 0 <= c[0] < 10 and 0 <= c[1] < 10
    assert cell1 == (5, 5)  # center
    print(f"  ✅ cell mapping: (0,0)={cell1}, (0.95,-0.95)={cell2}, (-0.95,0.95)={cell3}")


def test_me04_add_first_individual_accepted():
    """The first individual in a cell is always accepted."""
    me = HyperbolicMapElites(grid_size=8, coord_dim=4)
    v = np.array([0.5, 0.0, 0.0, 0.0])
    b = np.array([0.3, -0.2])
    accepted = me.add(v, b)
    assert accepted
    assert len(me.archive) == 1
    print(f"  ✅ first individual accepted (archive size: {len(me.archive)})")


def test_me05_add_better_replaces_worse():
    """A fitter individual in the same cell replaces the weaker one."""
    me = HyperbolicMapElites(grid_size=8, coord_dim=4)
    v_weak = np.array([0.5, 0.0, 0.0, 0.0])  # norm ~0.5 → fitness ~0.83
    v_strong = np.array([0.6, 0.0, 0.0, 0.0])  # norm 0.6 → fitness 1.0 (peak)
    b = np.array([0.3, -0.2])
    cell = me._behavior_to_cell(b)  # (0.3,-0.2) → (5, 3) on grid 8
    me.add(v_weak, b)
    accepted = me.add(v_strong, b)
    assert accepted, "better individual must replace worse"
    elite = me.archive[cell]
    assert elite.fitness > 0.9
    print(f"  ✅ better replaces worse (fitness: {elite.fitness:.3f}, cell: {cell})")


def test_me06_add_worse_rejected():
    """A weaker individual in the same cell is rejected."""
    me = HyperbolicMapElites(grid_size=8, coord_dim=4)
    v_strong = np.array([0.6, 0.0, 0.0, 0.0])
    v_weak = np.array([0.1, 0.0, 0.0, 0.0])
    b = np.array([0.3, -0.2])
    me.add(v_strong, b)
    accepted = me.add(v_weak, b)
    assert not accepted
    print(f"  ✅ worse individual rejected")


def test_me07_safe_mutate_accepts_in_bounds():
    """A small mutation that stays in the ball is accepted."""
    me = HyperbolicMapElites(coord_dim=4)
    parent = np.array([0.5, 0.0, 0.0, 0.0])
    def small_mutation(v):
        return v + np.array([0.01, 0.0, 0.0, 0.0])
    verdict = me.safe_mutate(parent, small_mutation, np.array([0.3, -0.2]))
    assert verdict.accepted
    assert verdict.ball_ok
    assert verdict.care_floor_ok
    print(f"  ✅ safe mutation accepted (delta={verdict.fitness_delta:.4f})")


def test_me08_safe_mutate_rejects_out_of_ball():
    """A mutation that pushes ||v|| past ball_radius is rejected."""
    me = HyperbolicMapElites(ball_radius=0.9, coord_dim=4)
    parent = np.array([0.5, 0.0, 0.0, 0.0])
    def out_of_ball_mutation(v):
        return v + np.array([100.0, 0.0, 0.0, 0.0])
    verdict = me.safe_mutate(parent, out_of_ball_mutation, np.array([0.3, -0.2]))
    assert not verdict.accepted
    assert not verdict.ball_ok
    assert "ball" in verdict.reason
    print(f"  ✅ out-of-ball mutation rejected: '{verdict.reason}'")


def test_me09_safe_mutate_rejects_catastrophic():
    """A mutation that crashes fitness by >50% is rejected."""
    me = HyperbolicMapElites(coord_dim=4)
    parent = np.array([0.6, 0.0, 0.0, 0.0])  # fitness 1.0
    def crash(v):
        return np.array([0.0, 0.0, 0.0, 0.0])  # fitness ~0
    verdict = me.safe_mutate(parent, crash, np.array([0.3, -0.2]))
    assert not verdict.accepted
    # The delta is huge negative
    assert verdict.fitness_delta < -0.3
    print(f"  ✅ catastrophic mutation rejected (delta={verdict.fitness_delta:.4f})")


def test_me10_iterate_grows_archive():
    """The iterate() loop grows the archive over iterations."""
    np.random.seed(42)
    me = HyperbolicMapElites(grid_size=8, coord_dim=4)
    for _ in range(5):
        v = np.random.randn(4) * 0.3
        b = np.clip(v[:2], -0.95, 0.95)
        me.add(v, b)
    initial_size = len(me.archive)
    result = me.iterate(n_iterations=30, seed=42)
    final_size = len(me.archive)
    assert final_size >= initial_size
    print(f"  ✅ iterate: {initial_size} → {final_size} cells, "
          f"accepted={result['accepted']}, rejected={result['rejected']}")


def test_me11_chain_id_audit():
    """Every mutation verdict has a 24-char chain_id."""
    me = HyperbolicMapElites(coord_dim=4)
    parent = np.array([0.5, 0.0, 0.0, 0.0])
    # Use a DETERMINISTIC mutation (no randomness) for this test
    def fixed_mutation(v):
        return v + np.array([0.01, 0.02, 0.03, 0.04])
    v = me.safe_mutate(parent, fixed_mutation, np.array([0.3, -0.2]))
    assert len(v.chain_id) == 24
    v2 = me.safe_mutate(parent, fixed_mutation, np.array([0.3, -0.2]))
    assert v.chain_id == v2.chain_id  # deterministic
    print(f"  ✅ chain_id is 24-char hex, deterministic")


def test_me12_stats_report():
    """stats() returns a complete picture."""
    np.random.seed(42)  # ensure reproducibility regardless of prior tests
    me = HyperbolicMapElites(grid_size=4, coord_dim=4)
    for _ in range(3):
        v = np.random.randn(4) * 0.3
        b = np.clip(v[:2], -0.95, 0.95)
        me.add(v, b)
    me.iterate(n_iterations=10, seed=42)
    s = me.stats()
    assert s["archive_size"] >= 3
    assert "fitness_max" in s
    assert "grid_coverage" in s
    print(f"  ✅ stats: archive={s['archive_size']}, max_fit={s['fitness_max']:.3f}, "
          f"coverage={s['grid_coverage']:.2%}")


def test_me13_canonical_constants():
    """The constants are the SOVOS substrate invariants."""
    assert CARE_FLOOR == 0.95
    assert MUTATION_REJECT_THRESHOLD > 0
    assert BALL_RADIUS < 1.0
    print(f"  ✅ canonical: care_floor={CARE_FLOOR}, reject_thresh={MUTATION_REJECT_THRESHOLD}, "
          f"ball_radius={BALL_RADIUS}")


def test_me14_self_test():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["archive_after_seed"] == 5
    assert info["archive_after_iter"] >= 5
    assert info["iter_accepted"] + info["iter_rejected"] == 20
    print(f"  ✅ self_test: {info}")


if __name__ == "__main__":
    tests = [
        test_me01_project_to_ball_keeps_in_ball,
        test_me02_project_to_ball_keeps_short_vectors,
        test_me03_behavior_to_cell_maps_to_grid,
        test_me04_add_first_individual_accepted,
        test_me05_add_better_replaces_worse,
        test_me06_add_worse_rejected,
        test_me07_safe_mutate_accepts_in_bounds,
        test_me08_safe_mutate_rejects_out_of_ball,
        test_me09_safe_mutate_rejects_catastrophic,
        test_me10_iterate_grows_archive,
        test_me11_chain_id_audit,
        test_me12_stats_report,
        test_me13_canonical_constants,
        test_me14_self_test,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
