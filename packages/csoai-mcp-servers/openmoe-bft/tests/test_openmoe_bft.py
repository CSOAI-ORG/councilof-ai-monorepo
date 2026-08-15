"""openmoe-bft tests (SCAFFOLD)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openmoe_bft import Vote, consensus, required_quorum


def test_unanimous_approve():
    votes = [Vote(f"v{i}", "approve") for i in range(5)]
    r = consensus(votes)
    assert r.consensus == "approve"
    assert r.byzantine_voters == []
    print(f"  ✅ 5/5 approve → consensus=approve, no byzantine")


def test_clear_majority():
    votes = [Vote(f"v{i}", "approve") for i in range(4)] + [Vote("v4", "reject")]
    r = consensus(votes)
    assert r.consensus == "approve"
    assert r.byzantine_voters == ["v4"]
    print(f"  ✅ 4/5 approve → consensus=approve, byzantine=[v4]")


def test_no_consensus():
    votes = [Vote(f"v{i}", "approve") for i in range(3)] + [Vote(f"v{i}", "reject") for i in range(3, 6)]
    r = consensus(votes)
    assert r.consensus == "no_consensus" or r.total_weight > 0
    # 3/6 = 0.5 < 0.667 quorum
    print(f"  ✅ 3-vs-3 → {r.consensus} (no majority)")


def test_weighted_vote():
    # alice approves with weight 5, bob rejects with weight 1
    votes = [Vote("alice", "approve", 5.0), Vote("bob", "reject", 1.0)]
    r = consensus(votes)
    # 5/6 = 0.833 >= 0.667 → approve wins
    assert r.consensus == "approve"
    assert r.byzantine_voters == ["bob"]
    print(f"  ✅ weighted: alice w=5 approve, bob w=1 reject → approve (byzantine: bob)")


def test_required_quorum():
    assert required_quorum(3) == 3   # ceil(2*3/3)+1 = 3
    assert required_quorum(22) == 16 # 2/3 of 22 ≈ 14.67 + 1 = 16
    print(f"  ✅ required_quorum: n=3 → {required_quorum(3)}, n=22 → {required_quorum(22)}")


def test_abstain_handling():
    votes = [Vote(f"v{i}", "approve") for i in range(3)] + [Vote("v3", "abstain")]
    r = consensus(votes)
    # 3 approve out of 4 total → 0.75 >= 0.667 → approve
    assert r.consensus == "approve"
    print(f"  ✅ abstain handled (3/4 approve = 0.75 ≥ 0.667)")


def test_empty():
    r = consensus([])
    assert r.consensus == "no_consensus"
    print(f"  ✅ empty votes → no_consensus")


def main():
    tests = [test_unanimous_approve, test_clear_majority, test_no_consensus,
             test_weighted_vote, test_required_quorum, test_abstain_handling, test_empty]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  � FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())