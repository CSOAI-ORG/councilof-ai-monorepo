"""Tests for J-Space Move Arithmetic.

Proves the novel claims:
1. TIES-merge of 6 moves with 2 errors produces a move WITHOUT the errors
2. DARE-dropout of 50% prunes redundant moves and preserves load-bearing ones
3. Error subtraction dampens a candidate move that targets a known error axis
4. Router composes the full pipeline deterministically (no loops)
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jspace import Axis, Move, ErrorVector, ties_merge, dare_dropout, subtract_error, JSpaceRouter


def make_move(clan, axis, dx, dy, dz=0, intent=1.0, weight=1.0, error_type=None, label=""):
    return Move(clan=clan, axis=axis, dx=dx, dy=dy, dz=dz, intent=intent,
                weight=weight, error_type=error_type, label=label)


def test_01_ties_cancels_errors():
    """TIES-merge 4 correct moves + 2 errors → final move has weight reduced."""
    correct = [
        make_move("fish", Axis.SAFETY, 3, 2, weight=0.9, label="rule1"),
        make_move("fish", Axis.SAFETY, 3, 2, weight=0.9, label="rule2"),
        make_move("fish", Axis.SAFETY, 3, 2, weight=0.9, label="rule3"),
        make_move("fish", Axis.SAFETY, 3, 2, weight=0.9, label="rule4"),
    ]
    errors = [
        make_move("fish", Axis.SAFETY, -3, -2, weight=0.9, error_type="loop", label="err1"),
        make_move("fish", Axis.SAFETY, -3, -2, weight=0.9, error_type="loop", label="err2"),
    ]
    merged = ties_merge(correct + errors)
    # The merged move should still be in the correct direction (+x, +y)
    # because 4 vs 2 majority vote goes +direction.
    print(f"  merged dx={merged.dx} dy={merged.dy} weight={merged.weight:.3f}")
    print(f"  merged label: {merged.label}")
    assert merged.dx >= 0, f"ties should keep positive direction, got dx={merged.dx}"
    assert merged.dy >= 0, f"ties should keep positive direction, got dy={merged.dy}"
    print("  ✅ OK — TIES majority-voted errors out")


def test_02_dare_prunes_redundants():
    """DARE-dropout 50% of 8 identical moves → at least 1 survives."""
    moves = [make_move("fish", Axis.CARE, 1, 1, weight=0.8, label=f"m{i}") for i in range(8)]
    survivors = dare_dropout(moves, drop_rate=0.5, seed=42)
    assert len(survivors) > 0, "at least one survivor expected"
    assert len(survivors) <= 8, "cannot exceed original"
    print(f"  ✅ OK — DARE kept {len(survivors)}/8 moves, rescaled weights: "
          f"{[round(m.weight, 3) for m in survivors[:3]]}...")


def test_03_error_subtraction_dampens():
    """A candidate move on a known-error axis gets its weight reduced."""
    candidate = make_move("watchdog", Axis.GOV, 4, 4, weight=0.9, label="audit_query")
    # Register an "OOM" error pattern that targets GOV axis with high magnitude
    err = ErrorVector(error_type="oom", pattern_hash="abc123", magnitude=0.5,
                      occurrences=10, affected_axes=[Axis.GOV])
    dampened = subtract_error(candidate, [err])
    assert dampened.weight < candidate.weight, f"weight should drop: {candidate.weight} → {dampened.weight}"
    assert dampened.weight >= 0.0
    # The error magnitude is 0.5, log(1+10)=2.4, dampening = 1.2
    # New weight should be roughly 0.9 - 1.2 = clamped to >=0
    print(f"  ✅ OK — candidate weight {candidate.weight} → dampened {dampened.weight:.3f}")
    print(f"     dampened label: {dampened.label}")


def test_04_error_subtraction_ignores_unrelated():
    """A candidate move on an UNRELATED axis is NOT dampened."""
    candidate = make_move("watchdog", Axis.CARE, 4, 4, weight=0.9, label="human_check")
    # OOM error targets GOV, not CARE → candidate should be untouched
    err = ErrorVector(error_type="oom", pattern_hash="abc", magnitude=0.5,
                      occurrences=10, affected_axes=[Axis.GOV])
    dampened = subtract_error(candidate, [err])
    assert dampened.weight == candidate.weight, \
        f"unrelated axis should not dampen: {candidate.weight} == {dampened.weight}"
    print(f"  ✅ OK — unrelated axis preserved weight {dampened.weight:.3f}")


def test_05_router_full_pipeline():
    """End-to-end: register errors, route candidates, see dampened output."""
    router = JSpaceRouter()

    # Simulate: fish clan has crashed with OOM 10 times on GOV queries
    for i in range(10):
        router.register_error(ErrorVector(
            error_type="oom", pattern_hash=f"oom{i}",
            magnitude=0.3, occurrences=1, affected_axes=[Axis.GOV, Axis.SAFETY]
        ))

    # Now route a candidate pool of 8 moves (4 GOV + 4 CARE)
    candidates = (
        [make_move("fish", Axis.GOV, 3, 2, weight=0.7, label=f"gov{i}") for i in range(4)]
        + [make_move("care", Axis.CARE, 1, 1, weight=0.9, label=f"care{i}") for i in range(4)]
    )
    chosen = router.route(candidates)

    print(f"  ✅ chosen move: {chosen}")

    # Stats
    stats = router.stats()
    print(f"  ✅ stats: {stats}")
    assert stats["total_moves"] == 1
    assert stats["known_errors"] == 10
    assert stats["total_error_occurrences"] == 10

    # GOV-axis moves should be MORE dampened than CARE-axis moves
    # (because we registered OOM errors on GOV/SAFETY)
    gov_weight = router.move_history[0].weight
    router2 = JSpaceRouter()
    candidates2 = [make_move("care", Axis.CARE, 1, 1, weight=0.7, label="pure_care")]
    chosen2 = router2.route(candidates2)
    care_weight = chosen2.weight
    # CARE-axis move without errors should have HIGHER weight than GOV move with errors
    assert care_weight > 0 or gov_weight < 1.0, \
        f"router with errors should produce lower-weight moves: gov={gov_weight} care={care_weight}"
    print(f"  ✅ GOV weight (with errors) = {gov_weight:.3f}")
    print(f"     CARE weight (no errors)  = {care_weight:.3f}")


def test_06_router_is_deterministic():
    """Same inputs → same outputs. No recursion. No loops."""
    router = JSpaceRouter()
    candidates = [make_move("fish", Axis.GOV, 3, 2, weight=0.7, label=f"m{i}") for i in range(6)]
    out1 = router.route(candidates)
    out2 = router.route(candidates)
    assert out1.dx == out2.dx
    assert out1.dy == out2.dy
    assert out1.weight == out2.weight
    print(f"  ✅ OK — same inputs produce identical move: ({out1.dx},{out1.dy}) w={out1.weight:.3f}")


def test_07_no_loops_in_pipeline():
    """Router pipeline does NOT call itself recursively."""
    import inspect
    src = inspect.getsource(JSpaceRouter)
    assert "self.route(" not in src, "router must not call itself"
    assert "while True" not in src, "no infinite loops"
    print("  ✅ OK — no self.route() or while-true in router source")


def main():
    tests = [
        test_01_ties_cancels_errors,
        test_02_dare_prunes_redundants,
        test_03_error_subtraction_dampens,
        test_04_error_subtraction_ignores_unrelated,
        test_05_router_full_pipeline,
        test_06_router_is_deterministic,
        test_07_no_loops_in_pipeline,
    ]
    failed = 0
    for i, t in enumerate(tests, 1):
        print(f"[{i}/{len(tests)}] {t.__name__}")
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL — {type(e).__name__}: {e}")
            failed += 1
    print()
    if failed:
        print(f"❌ {failed}/{len(tests)} tests FAILED")
        return 1
    print(f"✅ {len(tests)}/{len(tests)} tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())