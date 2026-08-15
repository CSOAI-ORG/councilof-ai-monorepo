"""Tests for csoai-alchemist v0.2.0 — the 6 geometry mutation operators.

20 tests covering:
- Each of the 6 operators (MOVE, SPAWN, MERGE, SPLIT, REWIRE, CURVATURE)
- apply_mutation() updates the registry correctly
- CURVATURE is human-sign only (refused by default)
- Universal mutate() dispatcher routes correctly
- Operator results stay in the Poincaré ball
- New MutableAlchemist is backward-compatible with Alchemist
"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sovos-jspace-hyperbolic" / "src"))

from csoai_alchemist import AlchemistConfig, ClanPosition
from csoai_alchemist.mutations import (
    MutationOp, MutationRecord, MutationConfig, MutableAlchemist,
)


def _norm(v):
    return math.sqrt(sum(x * x for x in v))


def _make_alchemist_with_clans(seed=42):
    """Helper: build an alchemist with 3 clans at different positions."""
    a = MutableAlchemist(config=AlchemistConfig(orphan_threshold=1.5),
                          mutation_config=MutationConfig(seed=seed))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    a.register_clan(ClanPosition("clan_1", (0.5, 0.1, 0.0)))
    a.register_clan(ClanPosition("clan_2", (0.8, 0.2, 0.1)))
    return a


# ----- Original 12 tests still pass -----

def test_01_empty_alchemist_marks_everything_orphan():
    a = MutableAlchemist()
    vecs = [("sv-1", (0.5, 0.0, 0.0))]
    proposals = a.scan(vecs)
    assert proposals == []
    print("  ✅ empty alchemist → no proposals")


def test_02_classify_orphan_below_threshold():
    a = _make_alchemist_with_clans()
    assert not a._classify_orphan((0.12, 0.0, 0.0), "sv-1")
    print("  ✅ near-vector: not orphan (backward compat)")


def test_03_classify_orphan_far_from_all_clans():
    a = _make_alchemist_with_clans()
    assert a._classify_orphan((0.95, 0.0, 0.0), "sv-1")
    print("  ✅ far-vector: orphan (backward compat)")


# ----- v0.2.0 new tests: 6 mutation operators -----

def test_04_move_perturbs_centroid():
    """MOVE: centroid changes, stays in ball."""
    a = _make_alchemist_with_clans()
    original = a.clans["clan_0"].centroid
    m = a.op_move("clan_0", step=0.05)
    assert m.op == MutationOp.MOVE
    assert m.parent_ids == ["clan_0"]
    assert m.new_centroid != original, "centroid should move"
    assert _norm(m.new_centroid) < 1.0, "centroid must stay in ball"
    print(f"  ✅ MOVE: ({original[0]:.3f},{original[1]:.3f}) → ({m.new_centroid[0]:.3f},{m.new_centroid[1]:.3f})")


def test_05_move_unknown_clan_refused():
    a = _make_alchemist_with_clans()
    m = a.op_move("nonexistent")
    assert m.accepted is False
    assert "unknown" in m.rationale.lower()
    print("  ✅ MOVE: unknown clan → refused")


def test_06_spawn_creates_new_clan():
    """SPAWN: new clan placed near boundary."""
    a = _make_alchemist_with_clans()
    m = a.op_spawn("clan_0", radius=0.7)
    assert m.op == MutationOp.SPAWN
    assert _norm(m.new_centroid) < 1.0
    assert _norm(m.new_centroid) > 0.3, "SPAWN should land far from origin"
    # Apply the mutation
    before_count = len(a.clans)
    a.apply_mutation(m)
    assert len(a.clans) == before_count + 1, "SPAWN should add a new clan"
    new_id = [k for k in a.clans if k not in ("clan_0", "clan_1", "clan_2")][0]
    assert a.clans[new_id].centroid == m.new_centroid
    print(f"  ✅ SPAWN: new clan '{new_id}' added (total: {len(a.clans)})")


def test_07_merge_fuses_close_clans():
    """MERGE: two close clans → Fréchet mean centroid."""
    a = MutableAlchemist(mutation_config=MutationConfig(merge_overlap_threshold=2.0))
    a.register_clan(ClanPosition("a", (0.1, 0.0, 0.0)))
    a.register_clan(ClanPosition("b", (0.12, 0.01, 0.0)))
    m = a.op_merge("a", "b")
    assert m.op == MutationOp.MERGE
    assert m.accepted is False  # not yet applied
    assert _norm(m.new_centroid) < 1.0
    # Apply
    a.apply_mutation(m)
    assert "b" not in a.clans, "merged clan should be deleted"
    assert "a" in a.clans
    print(f"  ✅ MERGE(a,b): 2 clans → 1, ||merged||={_norm(m.new_centroid):.4f}")


def test_08_merge_refuses_distant_clans():
    """MERGE: clans too far apart are refused."""
    a = MutableAlchemist(mutation_config=MutationConfig(merge_overlap_threshold=0.1))
    a.register_clan(ClanPosition("a", (0.1, 0.0, 0.0)))
    a.register_clan(ClanPosition("b", (0.9, 0.0, 0.0)))
    m = a.op_merge("a", "b")
    assert m.accepted is False
    assert "too far" in m.rationale
    print("  ✅ MERGE: distant clans refused")


def test_09_split_requires_min_members():
    """SPLIT: clans with too few members are refused."""
    a = _make_alchemist_with_clans()
    a.clans["clan_0"].member_ids = ["x"]  # only 1 member
    m = a.op_split("clan_0")
    assert m.accepted is False
    assert "too small" in m.rationale
    print("  ✅ SPLIT: small clan refused")


def test_10_split_produces_offspring_in_ball():
    """SPLIT: result is in the ball."""
    a = _make_alchemist_with_clans()
    a.clans["clan_0"].member_ids = ["x", "y", "z", "w", "v", "u"]  # 6 members
    m = a.op_split("clan_0")
    assert _norm(m.new_centroid) < 1.0
    print(f"  ✅ SPLIT: offspring ||c||={_norm(m.new_centroid):.4f}")


def test_11_rewire_updates_edge_weight():
    """REWIRE: changes edge weight by ~20%."""
    a = _make_alchemist_with_clans()
    a.add_edge("clan_0", "clan_1", weight=1.0)
    m = a.op_rewire("clan_0")
    assert m.op == MutationOp.REWIRE
    assert 0.99 < m.new_centroid[0] <= 1.0, "default rewire adds 20% → max 1.0"
    a.apply_mutation(m)
    assert a.edges["clan_0"]["clan_1"] == m.new_centroid[0]
    print(f"  ✅ REWIRE: 1.0 → {m.new_centroid[0]:.4f}")


def test_12_rewire_refused_when_no_edges():
    a = _make_alchemist_with_clans()
    m = a.op_rewire("clan_0")
    assert m.accepted is False
    assert "no edges" in m.rationale
    print("  ✅ REWIRE: no edges → refused")


def test_13_curvature_changes_radius():
    """CURVATURE: scales ||centroid|| by ±10%."""
    a = _make_alchemist_with_clans()
    m = a.op_curvature("clan_0", step=0.1)
    original_norm = _norm(a.clans["clan_0"].centroid)
    new_norm = _norm(m.new_centroid)
    # Step=0.1 means +10% of norm
    assert abs(new_norm - original_norm * 1.1) < 1e-6, \
        f"||c|| {original_norm:.4f} → {new_norm:.4f} (expected {original_norm*1.1:.4f})"
    print(f"  ✅ CURVATURE: ||c|| {original_norm:.4f} → {new_norm:.4f}")


def test_14_curvature_human_sign_only():
    """CURVATURE: apply_mutation() REFUSES unless explicitly human-signed."""
    a = _make_alchemist_with_clans()
    original_centroid = a.clans["clan_0"].centroid
    m = a.op_curvature("clan_0", step=0.1)
    # Default apply: refuses
    applied = a.apply_mutation(m)
    assert applied is False, "CURVATURE must refuse by default"
    assert a.clans["clan_0"].centroid == original_centroid, "centroid should be unchanged"
    # Human-sign override: accepts
    applied = a.apply_mutation_curvature_human_signed(m)
    assert applied is True
    assert a.clans["clan_0"].centroid != original_centroid
    print(f"  ✅ CURVATURE: default refused, human-sign accepted")


def test_15_universal_mutate_dispatcher():
    """mutate(op, **kwargs) routes to the right op_xxx."""
    a = _make_alchemist_with_clans()
    # Test each operator
    ops_with_kwargs = [
        (MutationOp.MOVE, {"target_id": "clan_0"}),
        (MutationOp.SPAWN, {"parent_id": "clan_1"}),
        (MutationOp.SPLIT, {"clan_id": "clan_2"}),
        (MutationOp.CURVATURE, {"target_id": "clan_0", "step": 0.05}),
    ]
    a.clans["clan_2"].member_ids = ["a", "b", "c", "d", "e", "f"]  # enable SPLIT
    for op, kwargs in ops_with_kwargs:
        m = a.mutate(op, **kwargs)
        assert m.op == op
        assert _norm(m.new_centroid) < 1.0, f"{op.value} result not in ball"
    # Test MERGE / REWIRE
    a.add_edge("clan_0", "clan_1")
    m = a.mutate(MutationOp.REWIRE, clan_id="clan_0")
    assert m.op == MutationOp.REWIRE
    m = a.mutate(MutationOp.MERGE, clan_a_id="clan_0", clan_b_id="clan_1")
    assert m.op == MutationOp.MERGE
    print("  ✅ mutate() dispatcher routes all 6 ops correctly")


def test_16_all_mutations_stay_in_ball():
    """Every mutation produces a centroid inside the open unit ball."""
    a = _make_alchemist_with_clans()
    a.add_edge("clan_0", "clan_1")
    a.clans["clan_0"].member_ids = ["a"] * 10  # allow SPLIT
    mutations = [
        a.op_move("clan_0", step=0.1),
        a.op_spawn("clan_1", radius=0.9),
        a.op_split("clan_0"),
        a.op_curvature("clan_0", step=0.5),
    ]
    for m in mutations:
        n = _norm(m.new_centroid)
        assert n < 1.0, f"{m.op.value}: ||c||={n} not in ball"
    print("  ✅ all 4 in-ball mutations produce unit-ball centroids")


def test_17_mutation_history_recorded():
    """Every mutation is appended to mutation_history."""
    a = _make_alchemist_with_clans()
    before = len(a.mutation_history)
    a.op_move("clan_0")
    a.op_spawn("clan_1")
    a.op_curvature("clan_0")
    assert len(a.mutation_history) - before == 3
    print(f"  ✅ mutation_history: {len(a.mutation_history)} records")


def test_18_curvature_zero_radius_refused():
    """CURVATURE: clan at origin can't be curved (zero norm)."""
    a = _make_alchemist_with_clans()
    a.register_clan(ClanPosition("origin", (0.0, 0.0, 0.0)))
    m = a.op_curvature("origin", step=0.1)
    assert m.accepted is False
    assert "zero" in m.rationale.lower()
    print("  ✅ CURVATURE: zero-radius clan refused")


def test_19_spawn_refused_for_unknown_parent():
    a = _make_alchemist_with_clans()
    m = a.op_spawn("nonexistent")
    assert m.accepted is False
    assert "unknown" in m.rationale.lower()
    print("  ✅ SPAWN: unknown parent refused")


def test_20_move_unknown_clan_no_mutation_applied():
    """MOVE on unknown clan: accepted=False; apply_mutation returns False."""
    a = _make_alchemist_with_clans()
    m = a.op_move("nonexistent")
    assert m.accepted is False
    applied = a.apply_mutation(m)
    assert applied is False
    print("  ✅ MOVE: unknown clan → not applied")


def main():
    tests = [
        test_01_empty_alchemist_marks_everything_orphan,
        test_02_classify_orphan_below_threshold,
        test_03_classify_orphan_far_from_all_clans,
        test_04_move_perturbs_centroid,
        test_05_move_unknown_clan_refused,
        test_06_spawn_creates_new_clan,
        test_07_merge_fuses_close_clans,
        test_08_merge_refuses_distant_clans,
        test_09_split_requires_min_members,
        test_10_split_produces_offspring_in_ball,
        test_11_rewire_updates_edge_weight,
        test_12_rewire_refused_when_no_edges,
        test_13_curvature_changes_radius,
        test_14_curvature_human_sign_only,
        test_15_universal_mutate_dispatcher,
        test_16_all_mutations_stay_in_ball,
        test_17_mutation_history_recorded,
        test_18_curvature_zero_radius_refused,
        test_19_spawn_refused_for_unknown_parent,
        test_20_move_unknown_clan_no_mutation_applied,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
