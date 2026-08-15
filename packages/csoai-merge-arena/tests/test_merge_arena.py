"""Tests for csoai-merge-arena — merge regression with statistical teeth."""
from __future__ import annotations

import pytest
from csoai_merge_arena import (
    ARENA_AXES,
    DEFAULT_AXIS_N,
    DEFAULT_SPECIALISTS,
    AxisResult,
    EliteCell,
    MAPElitesMergeArchive,
    MergeGenome,
    MergeRegressionResult,
    MergeSpec,
    run_arena,
    sample_merge_space,
)


def test_01_arena_axes_count():
    """12 canonical GSPC axes."""
    assert len(ARENA_AXES) == 12
    for ax in ["gov", "prv", "asi", "mcp", "oss", "mach", "care", "det", "art5", "swarm"]:
        assert ax in ARENA_AXES


def test_02_run_arena_no_regression_when_child_better():
    parent = {a: 0.5 for a in ARENA_AXES}
    child = {a: 0.6 for a in ARENA_AXES}
    r = run_arena(parent, child, n_per_axis=40)
    assert r.is_safe_to_merge
    assert not r.any_regression()
    assert r.worst_axis() is None


def test_03_run_arena_flags_regression():
    parent = {a: 0.9 for a in ARENA_AXES}
    child = {a: 0.9 for a in ARENA_AXES}
    child["gov"] = 0.5  # catastrophic drop on gov
    r = run_arena(parent, child, n_per_axis=40)
    assert r.any_regression()
    assert not r.is_safe_to_merge
    worst = r.worst_axis()
    assert worst is not None
    assert worst.axis == "gov"


def test_04_wilson_ci_bounds():
    a = AxisResult(axis="gov", n=30, n_permitted=24, mean_confidence=0.8, is_regression=False)
    lo, hi = a.wilson_ci()
    assert 0.0 <= lo <= a.proportion <= hi <= 1.0


def test_05_wilson_ci_widens_for_small_n():
    """Smaller n → wider CI. n=30 vs n=300 should give different CI widths."""
    a30 = AxisResult(axis="x", n=30, n_permitted=20, mean_confidence=0.66, is_regression=False)
    a300 = AxisResult(axis="x", n=300, n_permitted=200, mean_confidence=0.66, is_regression=False)
    lo30, hi30 = a30.wilson_ci()
    lo300, hi300 = a300.wilson_ci()
    width30 = hi30 - lo30
    width300 = hi300 - lo300
    assert width30 > width300


def test_06_n_minimum_required():
    """is_safe requires n ≥ DEFAULT_AXIS_N on every axis."""
    parent = {a: 0.5 for a in ARENA_AXES}
    child = {a: 0.6 for a in ARENA_AXES}
    r_safe = run_arena(parent, child, n_per_axis=30)
    assert r_safe.is_safe_to_merge
    r_unsafe = run_arena(parent, child, n_per_axis=10)  # too few
    assert not r_unsafe.is_safe_to_merge


def test_07_chain_id_deterministic():
    parent = {"gov": 0.5, "care": 0.5}
    child = {"gov": 0.6, "care": 0.7}
    r1 = run_arena(parent, child)
    r2 = run_arena(parent, child)
    assert r1.chain_id == r2.chain_id
    assert len(r1.chain_id) == 32


def test_08_merge_spec_fingerprint_stable():
    spec = MergeSpec(
        merge_id="m1",
        base_model="qwen2.5:0.5b",
        specialists=["governance", "safety"],
        weights={"governance": 0.6, "safety": 0.4},
    )
    f1 = spec.fingerprint()
    f2 = spec.fingerprint()
    assert f1 == f2
    assert len(f1) == 16


def test_09_merge_spec_fingerprint_changes_with_config():
    a = MergeSpec(merge_id="m1", base_model="q", specialists=["x"], weights={"x": 1.0})
    b = MergeSpec(merge_id="m2", base_model="q", specialists=["x"], weights={"x": 1.0})
    assert a.fingerprint() != b.fingerprint()


def test_10_map_elites_empty_archive():
    arc = MAPElitesMergeArchive()
    assert arc.coverage == 0.0
    assert arc.best_by_fitness() is None


def test_11_map_elites_add_inserts():
    arc = MAPElitesMergeArchive(bins=10)
    g = MergeGenome(lam=0.5, density=0.5, dare_dropout=0.1, weight_vector=(0.25,)*4)
    inserted = arc.add(g, safety_retention=0.9, capability_gain=0.8, sigma_cost=0.1)
    assert inserted
    assert arc.coverage > 0
    assert arc.best_by_fitness() is not None


def test_12_map_elites_replaces_only_on_improvement():
    arc = MAPElitesMergeArchive(bins=10)
    g = MergeGenome(lam=0.5, density=0.5, dare_dropout=0.1, weight_vector=(0.25,)*4)
    arc.add(g, safety_retention=0.9, capability_gain=0.8, sigma_cost=0.1)
    # weaker genome in same cell — should NOT replace
    weak = MergeGenome(lam=0.4, density=0.4, dare_dropout=0.2, weight_vector=(0.5, 0.3, 0.1, 0.1))
    arc.add(weak, safety_retention=0.5, capability_gain=0.5, sigma_cost=0.4)
    best = arc.best_by_fitness()
    assert best.genome.lam == 0.5  # the original was kept


def test_13_map_elites_fitness_function():
    arc = MAPElitesMergeArchive(bins=10)
    # retention=1.0, gain=1.0, sigma=0.0 → fitness = 2.0
    assert arc.fitness(1.0, 1.0, 0.0) == 2.0
    # retention=0, gain=0, sigma=1.0 → fitness = -0.5
    assert arc.fitness(0.0, 0.0, 1.0) == -0.5


def test_14_sample_merge_space_size():
    """Default sample is 16 genomes."""
    genomes = sample_merge_space(n=16)
    assert len(genomes) == 16


def test_15_sample_merge_space_weights_sum_to_one():
    """Each genome's weight vector should sum to ~1.0."""
    for g in sample_merge_space(n=10):
        s = sum(g.weight_vector)
        assert abs(s - 1.0) < 1e-6


def test_16_sample_merge_space_seed_deterministic():
    a = sample_merge_space(seed=42)
    b = sample_merge_space(seed=42)
    for g1, g2 in zip(a, b):
        assert g1.lam == g2.lam
        assert g1.density == g2.density


def test_17_merge_genome_key_discretises():
    g1 = MergeGenome(lam=0.501, density=0.502, dare_dropout=0.1, weight_vector=(0.25,)*4)
    g2 = MergeGenome(lam=0.504, density=0.499, dare_dropout=0.1, weight_vector=(0.25,)*4)
    assert g1.key() == g2.key()  # both round to 0.50


def test_18_axis_count_matches_12():
    """The arena covers the canonical 12 GSPC axes."""
    parent = {a: 0.5 for a in ARENA_AXES}
    child = {a: 0.6 for a in ARENA_AXES}
    r = run_arena(parent, child)
    assert len(r.axes) == 12


def test_19_no_kinetic_in_safety_retention():
    """safety_retention is a fitness concept, not a kinetic one."""
    arc = MAPElitesMergeArchive(bins=10)
    g = MergeGenome(lam=0.5, density=0.5, dare_dropout=0.1, weight_vector=(0.25,)*4)
    arc.add(g, safety_retention=0.9, capability_gain=0.8, sigma_cost=0.1)
    d = arc.to_dict()
    text = str(d).lower()
    assert "kinetic" not in text
    assert "weapon" not in text
    assert "kill chain" not in text


def test_20_merge_spec_round_trip():
    spec = MergeSpec(
        merge_id="x",
        base_model="b",
        specialists=["a", "b"],
        weights={"a": 0.5, "b": 0.5},
    )
    d = spec.to_dict()
    assert d["merge_id"] == "x"
    assert d["weights"]["a"] == 0.5