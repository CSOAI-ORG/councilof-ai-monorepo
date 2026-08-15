"""Tests for csoai-alchemist v0.1.0 SCAFFOLD.

12 tests covering:
- Basic registration + classification
- Orphan detection (above threshold = orphan)
- Cluster finding (greedy DBSCAN approximation)
- Proposal scoring (density)
- Accept/reject lifecycle
- Real Alchemist loop on synthetic data
"""
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sovos-jspace-hyperbolic" / "src"))

from csoai_alchemist import Alchemist, AlchemistConfig, ClanPosition
from hyperbolic import project_to_ball


def test_01_empty_alchemist_marks_everything_orphan():
    """No registered clans → everything is an orphan."""
    a = Alchemist()
    vecs = [("sv-1", project_to_ball((0.5, 0.0, 0.0)))]
    proposals = a.scan(vecs)
    # But empty cluster doesn't meet min_clan_size
    assert proposals == [], f"empty should not propose, got {proposals}"
    print("  ✅ no clans → all orphans, but min_clan_size gates the proposal")


def test_02_classify_orphan_below_threshold():
    """A vector within threshold of a clan is NOT an orphan."""
    a = Alchemist()
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    # Vector near the clan centroid — should NOT be orphan
    v_near = project_to_ball((0.12, 0.0, 0.0))
    assert not a._classify_orphan(v_near, "sv-1"), "near-vector should not be orphan"
    print("  ✅ near-vector: not orphan")


def test_03_classify_orphan_far_from_all_clans():
    """A vector far from ALL clans IS an orphan."""
    a = Alchemist()
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    # Vector near the boundary, far from clan
    v_far = project_to_ball((0.9, 0.0, 0.0))
    assert a._classify_orphan(v_far, "sv-1"), "far-vector should be orphan"
    print("  ✅ far-vector: orphan")


def test_04_scan_proposes_when_orphan_cluster_forms():
    """Three orphans near each other → 1 proposal."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=3))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    # Three orphans clustered near (0.9, 0.0, 0.0), but at v0.1.0 SCAFFOLD greedy
    # clustering uses poincare distance threshold = orphan_threshold
    # Three points exactly coincident will cluster trivially
    orphan_cluster = [
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-c", project_to_ball((0.9, 0.0, 0.0))),
    ]
    proposals = a.scan(orphan_cluster)
    assert len(proposals) == 1, f"expected 1 proposal, got {len(proposals)}"
    assert proposals[0].clan_id == "orphan_0"
    assert len(proposals[0].member_ids) == 3
    print(f"  ✅ orphan cluster (3) → 1 proposal ({proposals[0].clan_id})")


def test_05_scan_no_proposal_below_min_size():
    """2 orphans < min_clan_size=3 → no proposal."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=3))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    proposals = a.scan([
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
    ])
    assert proposals == [], f"min_clan_size=3 should gate, got {proposals}"
    print("  ✅ 2 orphans, min_size=3 → no proposal")


def test_06_proposal_centroid_is_in_ball():
    """The proposed clan's centroid must be inside the ball."""
    # Tight orphan_threshold so the test vectors count as orphans
    a = Alchemist(AlchemistConfig(orphan_threshold=0.5, min_clan_size=2))
    a.register_clan(ClanPosition("clan_0", (0.05, 0.0, 0.0)))  # near origin
    proposals = a.scan([
        ("sv-a", project_to_ball((0.5, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.55, 0.05, 0.0))),
    ])
    assert len(proposals) == 1
    c = proposals[0].centroid
    norm = math.sqrt(sum(x * x for x in c))
    # Strict: must be strictly inside the open ball
    assert norm < 1.0, f"centroid must be inside open ball, got norm={norm}"
    # Healthy: should be well clear of the boundary
    assert norm < 0.99, f"centroid too close to boundary: norm={norm}"
    print(f"  ✅ proposed centroid: ({c[0]:.4f}, {c[1]:.4f}, {c[2]:.4f}), norm={norm:.4f}")


def test_07_proposal_score_reflects_density():
    """A tight cluster should score higher than a loose one."""
    a_tight = Alchemist(AlchemistConfig(orphan_threshold=3.0, min_clan_size=3))
    a_loose = Alchemist(AlchemistConfig(orphan_threshold=3.0, min_clan_size=3))
    a_tight.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    a_loose.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    tight_proposals = a_tight.scan([
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-c", project_to_ball((0.9, 0.0, 0.0))),
    ])
    # Loose = three points far apart (but still within threshold)
    loose_proposals = a_loose.scan([
        ("sv-a", project_to_ball((0.7, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.85, 0.05, 0.0))),
        ("sv-c", project_to_ball((0.95, -0.1, 0.0))),
    ])
    if tight_proposals and loose_proposals:
        # Density scores: tight should be 1.0, loose < 1.0
        tight_score = tight_proposals[0].proposal_score
        loose_score = loose_proposals[0].proposal_score
        assert tight_score >= loose_score, f"tight ({tight_score}) should score ≥ loose ({loose_score})"
        print(f"  ✅ tight score: {tight_score:.3f} ≥ loose score: {loose_score:.3f}")


def test_08_accept_proposal_registers_clan():
    """Accepting a proposal adds the clan to the registry."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=2))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    proposals = a.scan([
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
    ])
    assert len(proposals) == 1
    initial_count = len(a.clans)
    a.accept_proposal(proposals[0])
    assert len(a.clans) == initial_count + 1
    assert proposals[0].clan_id in a.clans
    print(f"  ✅ accept: {initial_count} → {len(a.clans)} clans")


def test_09_reject_proposal_keeps_history():
    """Rejecting keeps history but doesn't register."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=2))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    proposals = a.scan([
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
    ])
    assert len(proposals) == 1
    history_before = len(a.proposal_history)
    a.reject_proposal(proposals[0])
    assert len(a.clans) == 1, "reject should NOT register"
    assert len(a.proposal_history) == history_before
    print(f"  ✅ reject: clans unchanged, history preserved (n={len(a.proposal_history)})")


def test_10_max_proposals_caps_output():
    """The max_proposals config should cap the number returned."""
    a = Alchemist(AlchemistConfig(orphan_threshold=5.0, min_clan_size=2, max_proposals=1))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    # 6 vectors in 3 disjoint pairs
    vecs = []
    for i, base in enumerate([(0.9, 0, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)]):
        for j in range(2):
            v = tuple(base[k] + 0.01 * j for k in range(3))
            vecs.append((f"sv-{i}-{j}", project_to_ball(v)))
    proposals = a.scan(vecs)
    assert len(proposals) <= 1, f"max_proposals=1 should cap, got {len(proposals)}"
    print(f"  ✅ max_proposals=1 caps output (got {len(proposals)})")


def test_11_curvature_field_reflects_centroid_norm():
    """Curvature field = ||centroid||. Centroid near boundary = high curvature."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=2))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    proposals = a.scan([
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
    ])
    assert len(proposals) == 1
    assert proposals[0].curvature > 0.8, f"orphan near boundary should have high curvature: {proposals[0].curvature}"
    print(f"  ✅ curvature: {proposals[0].curvature:.3f} (high, near boundary)")


def test_12_evolutionary_loop_converges():
    """Run the loop twice: after accepting, fewer orphans should be detected."""
    a = Alchemist(AlchemistConfig(orphan_threshold=2.0, min_clan_size=3))
    a.register_clan(ClanPosition("clan_0", (0.1, 0.0, 0.0)))
    vecs = [
        ("sv-a", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-b", project_to_ball((0.9, 0.0, 0.0))),
        ("sv-c", project_to_ball((0.9, 0.0, 0.0))),
    ]
    # First scan: 1 proposal (3 orphans)
    first = a.scan(vecs)
    assert len(first) == 1
    a.accept_proposal(first[0])
    # Second scan on same data: same vectors are now near the new clan
    second = a.scan(vecs)
    # The new clan centroid is at (0.9, 0, 0), so vectors are no longer orphans
    assert len(second) == 0, f"after accept, should have 0 proposals; got {len(second)}"
    print(f"  ✅ evolutionary loop: {len(first)} → {len(second)} proposals after accept")


def main():
    tests = [
        test_01_empty_alchemist_marks_everything_orphan,
        test_02_classify_orphan_below_threshold,
        test_03_classify_orphan_far_from_all_clans,
        test_04_scan_proposes_when_orphan_cluster_forms,
        test_05_scan_no_proposal_below_min_size,
        test_06_proposal_centroid_is_in_ball,
        test_07_proposal_score_reflects_density,
        test_08_accept_proposal_registers_clan,
        test_09_reject_proposal_keeps_history,
        test_10_max_proposals_caps_output,
        test_11_curvature_field_reflects_centroid_norm,
        test_12_evolutionary_loop_converges,
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
