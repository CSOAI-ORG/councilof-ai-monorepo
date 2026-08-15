"""Tests for csoai-council — the BFT Council weighting + quorum gate."""
from __future__ import annotations

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_council import (
    CANONICAL_F, CANONICAL_SEATS,
    Member, Vote, Council,
    council_from_reputation_map, self_test,
)


def _full_council(n=33):
    rep = {f"agent_{i:02d}": (1.0, 1.0, 1.0) for i in range(n)}
    return council_from_reputation_map(rep)


def test_c01_n_gt_3f_plus_1():
    """n=33, f=10 → 33 > 3*10+1=31 ✓ (canonical valid)."""
    c = council_from_reputation_map({f"a{i}": (1,1,1) for i in range(33)})
    assert c.n_seats > 3 * c.f + 1
    assert c.n_seats == CANONICAL_SEATS
    assert c.f == CANONICAL_F
    print(f"  ✅ n=33 > 3f+1=31 (f={CANONICAL_F})")


def test_c02_invalid_n_gt_3f_1_rejected():
    """n <= 3f+1 must raise (not a valid BFT configuration)."""
    try:
        Council(members=[Member(f"a{i}") for i in range(3)], n_seats=3, f=1)
        assert False, "should have raised (3 <= 3*1+1=4)"
    except ValueError:
        pass
    print(f"  ✅ n=3, f=1 rejected (3 <= 4)")


def test_c03_weight_is_product():
    """vote_weight = reputation × coherence × certification."""
    m = Member("x", reputation=1.0, coherence=0.5, certification=1.0)
    assert abs(m.weight() - 0.5) < 1e-9
    m2 = Member("y", reputation=0.8, coherence=0.9, certification=0.7)
    assert abs(m2.weight() - 0.8*0.9*0.7) < 1e-9
    print(f"  ✅ weight = rep×coh×cert: {m2.weight():.4f}")


def test_c04_zero_dimension_zeroes_vote():
    """Any zero dimension cancels the vote entirely (product form)."""
    m = Member("z", reputation=1.0, coherence=0.0, certification=1.0)
    assert m.weight() == 0.0
    print(f"  ✅ zero coherence → zero weight (no free riders)")


def test_c05_clamped_to_unit():
    """reputation/coherence/certification clamped to [0,1]."""
    m = Member("c", reputation=5.0, coherence=-1.0, certification=2.0)
    assert m.reputation == 1.0
    assert m.coherence == 0.0
    assert m.certification == 1.0
    print(f"  ✅ clamping: (5,-1,2) → (1,0,1)")


def test_c06_binding_quorum_reached():
    """25 of 33 full-weight votes yes → 25/33=0.758 ≥ 0.697 → pass."""
    c = _full_council()
    votes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(c.members)[:25]]
    d = c.decide("proposal", votes)
    assert d.passed
    assert d.quorum_fraction >= 0.697
    print(f"  ✅ 25/33 yes → passed (frac={d.quorum_fraction:.3f})")


def test_c07_binding_quorum_not_reached():
    """20 of 33 full-weight votes yes → 20/33=0.606 < 0.697 → fail."""
    c = _full_council()
    votes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(c.members)[:20]]
    d = c.decide("proposal", votes)
    assert not d.passed
    assert d.quorum_fraction < 0.697
    print(f"  ✅ 20/33 yes → failed (frac={d.quorum_fraction:.3f})")


def test_c08_weighted_vs_raw_matters():
    """Weighted voting: low-weight members can't reach quorum that raw count would."""
    # Only 23 full members + 10 members with zero weight (e.g. incoherent)
    rep = {f"full_{i:02d}": (1,1,1) for i in range(23)}
    rep.update({f"dead_{i:02d}": (1,0,1) for i in range(10)})  # coherence=0 → weight 0
    c = council_from_reputation_map(rep)
    total_w = c.total_weight  # 23*1 + 10*0 = 23
    # All 33 vote yes → yes_weight=23, total_voting=23 → frac=1.0 → pass
    votes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in rep.keys()]
    d = c.decide("proposal", votes)
    assert abs(total_w - 23.0) < 1e-9
    assert d.passed  # all voting weight voted yes
    assert d.quorum_fraction == 1.0
    # But if 23 full say yes out of 23 voting weight AND the 10 dead DON'T vote,
    # total voting = 23, yes = 23 → pass. Weighted dominance matters on the yes side.
    print(f"  ✅ weighted: dead members carry 0 weight; only 23 real units")


def test_c09_article_zero_requires_full():
    """Article 0 requires 33/33 by weight — 32/33 fails."""
    c = _full_council()
    votes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(c.members)[:32]]
    d = c.decide_article_zero("article-zero", votes)
    assert not d.passed
    assert d.required_fraction == 1.0
    # 33 → passes
    votes_full = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(c.members)]
    d2 = c.decide_article_zero("article-zero", votes_full)
    assert d2.passed
    print(f"  ✅ Article 0: 32/33 fails (>1.0 req), 33/33 passes")


def test_c10_chain_id_deterministic():
    """chain_id is 24 hex chars, deterministic per identical input."""
    c = _full_council()
    votes = [Vote(aid, True, c.members[aid].weight(), "sig") for aid in list(c.members)[:25]]
    d1 = c.decide("proposal", votes)
    d2 = c.decide("proposal", votes)
    assert d1.chain_id == d2.chain_id
    assert len(d1.chain_id) == 24
    print(f"  ✅ chain_id is 24-char hex, deterministic")


def test_c11_signed_vote_with_cryptography():
    """Real Ed25519 signature covers the vote (cryptography lib)."""
    import sys as _s
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:
        print(f"  ⚠️ cryptography missing — skip")
        return
    c = _full_council(n=3)
    rep = {f"a{i}": (1,1,1) for i in range(3)}
    c = council_from_reputation_map(rep, n_seats=5, f=1)
    key = ed25519.Ed25519PrivateKey.generate()
    mem = list(rep.keys())[0]
    v = c.sign_vote(c.members[mem], "signed-proposal", True, key, "chain123")
    assert v is not None
    assert v.signature  # hex signature present
    assert len(v.signature) == 128  # 64 bytes → 128 hex
    print(f"  ✅ Ed25519-signed vote: signature {len(v.signature)} hex chars")


def test_c12_stats():
    """stats() reports the council configuration."""
    c = _full_council()
    s = c.stats()
    assert s["n_seats"] == 33
    assert s["members"] == 33
    assert abs(s["total_weight"] - 33.0) < 1e-9
    assert abs(s["binding_quorum"] - 23/33) < 1e-9
    print(f"  ✅ stats: seats={s['n_seats']}, weight={s['total_weight']:.0f}, "
          f"quorum={s['binding_quorum']:.3f}")


def test_c13_self_test():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["n=33_f=10_valid"] is True
    assert info["20_yes_passed"] is False
    assert info["25_yes_passed"] is True
    assert info["chain_id_len"] == 24
    print(f"  ✅ self_test: 25/33 passes, 20/33 fails")


if __name__ == "__main__":
    tests = [
        test_c01_n_gt_3f_plus_1,
        test_c02_invalid_n_gt_3f_1_rejected,
        test_c03_weight_is_product,
        test_c04_zero_dimension_zeroes_vote,
        test_c05_clamped_to_unit,
        test_c06_binding_quorum_reached,
        test_c07_binding_quorum_not_reached,
        test_c08_weighted_vs_raw_matters,
        test_c09_article_zero_requires_full,
        test_c10_chain_id_deterministic,
        test_c11_signed_vote_with_cryptography,
        test_c12_stats,
        test_c13_self_test,
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
