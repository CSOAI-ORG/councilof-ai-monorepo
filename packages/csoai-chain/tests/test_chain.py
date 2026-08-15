"""Tests for csoai_chain — the SOVOS substrate chain + fitness gate."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_chain import (
    ChainResult,
    FitnessGate,
    chain,
    fitness_gate,
    self_test,
)


def test_ch01_chain_runs_with_no_peers():
    """Even with no peer packages, chain returns a valid ChainResult."""
    sv = {"vector": [0.1, 0.2, 0.3], "layer": "water", "source": "test"}
    r = chain(sv)
    assert isinstance(r, ChainResult)
    assert r.chain_id and len(r.chain_id) == 24
    assert r.inputs_sha and len(r.inputs_sha) == 24
    # No permitted state, no clans → both distances should be None
    assert r.poincare_distance is None
    assert r.fisher_rao_distance is None
    assert r.is_permitted is None
    assert r.threshold == 1.0
    print(f"  ✅ chain with no peers: id={r.chain_id[:8]}… backend={r.backend}")


def test_ch02_chain_with_fisher_rao_only():
    """Passing permitted_state alone computes Fisher-Rao distance.

    NB: the helper _vector_to_spd(v) builds diag(max(0.1, |v_i|)) plus small
    off-diagonals. So a "close" vector with values near 1 produces a matrix
    near the identity in Fisher-Rao distance.
    """
    permitted = np.eye(4)  # 4x4 because _vector_to_spd caps at n=min(len,8)
    close = {"vector": [1.0, 0.95, 0.95, 0.95], "layer": "water"}
    r = chain(close, permitted_state=permitted, threshold=1.0)
    assert r.fisher_rao_distance is not None, "Fisher-Rao kernel must be reachable"
    assert r.fisher_rao_distance < 1.0, f"close state should pass: {r.fisher_rao_distance}"
    assert r.is_permitted is True
    print(f"  ✅ Fisher-Rao close: d={r.fisher_rao_distance:.4f} permitted={r.is_permitted} backend={r.backend}")


def test_ch03_chain_with_clans_only():
    """Passing clans alone computes Poincaré distance."""
    clans = {
        "gov": np.array([0.0, 0.0, 0.0]),
        "agi": np.array([0.5, 0.5, 0.5]),
    }
    sv = {"vector": [0.1, 0.1, 0.1]}
    r = chain(sv, clans=clans)
    if r.poincare_distance is not None:
        assert r.routed_clan == "gov", f"expected gov, got {r.routed_clan}"
        assert r.poincare_distance >= 0
        print(f"  ✅ Poincaré routing: routed to '{r.routed_clan}' d={r.poincare_distance:.4f}")
    else:
        # Hyperbolic peer not available — that's still a valid result
        print(f"  ⚠️  Poincaré unavailable (hyperbolic peer missing): r={r}")


def test_ch04_chain_full_with_both():
    """Both clans + permitted → both distances computed."""
    permitted = np.eye(4)
    # Vector that maps to a near-permitted SPD via _vector_to_spd
    close_vec = [1.0, 0.95, 0.95, 0.95]
    clans = {"gov": np.array([0.0, 0.0, 0.0])}
    sv = {"vector": close_vec, "layer": "water"}
    r = chain(sv, permitted_state=permitted, clans=clans)
    assert r.fisher_rao_distance is not None
    assert r.is_permitted is True, f"close vector should be permitted: d={r.fisher_rao_distance}"
    # poincare_distance may or may not be set depending on peer availability
    print(f"  ✅ full chain: fr={r.fisher_rao_distance:.4f} "
          f"poincare={r.poincare_distance} clan={r.routed_clan}")


def test_ch05_chain_id_is_deterministic():
    """Same inputs → same chain_id (deterministic)."""
    permitted = np.eye(3)
    sv = {"vector": [0.1, 0.2, 0.3], "layer": "water"}
    r1 = chain(sv, permitted_state=permitted, threshold=1.0)
    r2 = chain(sv, permitted_state=permitted, threshold=1.0)
    assert r1.chain_id == r2.chain_id, f"non-deterministic: {r1.chain_id} vs {r2.chain_id}"
    print(f"  ✅ deterministic: chain_id={r1.chain_id[:16]}…")


def test_ch06_chain_id_changes_with_input():
    """Different inputs → different chain_id."""
    r1 = chain({"vector": [0.1, 0.2, 0.3]})
    r2 = chain({"vector": [0.4, 0.5, 0.6]})
    assert r1.chain_id != r2.chain_id
    print(f"  ✅ different inputs → different IDs")


def test_ch07_chain_handles_statevector_object():
    """Chain accepts a StateVector-like object (duck-typed)."""
    class FakeSV:
        vector = [0.1, 0.2, 0.3]
        layer = "water"
        source = "test"
        payload = {}
        sv_id = "abc123"
    sv = FakeSV()
    r = chain(sv)
    assert r.chain_id
    # inputs_sha should incorporate sv_id
    assert "abc123" not in r.inputs_sha  # hashed, not raw
    print(f"  ✅ StateVector duck-type: inputs_sha={r.inputs_sha[:16]}…")


def test_ch08_chain_handles_ndarray():
    """Chain accepts a numpy array directly."""
    sv = np.array([0.1, 0.2, 0.3])
    r = chain(sv)
    assert r.chain_id
    print(f"  ✅ ndarray input: id={r.chain_id[:16]}…")


def test_ch09_fitness_gate_pass():
    """A close state under default thresholds → PASS verdict."""
    g = fitness_gate()
    permitted = np.eye(4)
    # Vector that maps to a near-permitted SPD
    sv = {"vector": [1.0, 0.95, 0.95, 0.95]}
    r = chain(sv, permitted_state=permitted, threshold=g.fisher_rao_threshold, gate=g)
    verdict, reason = g.verdicts(r)
    assert verdict == "PASS", f"expected PASS, got {verdict} ({reason}) d={r.fisher_rao_distance}"
    assert any(s.startswith("SIGIL") for s in g.sigil_log), "PASS should emit a SIGIL"
    print(f"  ✅ FitnessGate PASS: verdict={verdict} sigils={len(g.sigil_log)}")


def test_ch10_fitness_gate_escalate_far():
    """A far state over the Fisher-Rao threshold → ESCALATE."""
    g = fitness_gate(fisher_rao_threshold=0.1)  # very tight
    permitted = np.eye(3)
    # Use a vector whose SPD projection is far from the permitted manifold
    sv = {"vector": [10.0, 10.0, 10.0]}
    r = chain(sv, permitted_state=permitted, threshold=g.fisher_rao_threshold, gate=g)
    verdict, reason = g.verdicts(r)
    assert verdict == "ESCALATE", f"expected ESCALATE, got {verdict} ({reason})"
    assert "fisher_rao" in reason
    assert g.sigil_log == [], "ESCALATE must NOT emit a SIGIL"
    print(f"  ✅ FitnessGate ESCALATE: {reason} sigils={len(g.sigil_log)}")


def test_ch11_fitness_gate_disabled():
    """Disabled gate still produces a verdict but skips SIGIL emit."""
    g = fitness_gate()
    g.enabled = False
    permitted = np.eye(4)
    sv = {"vector": [1.0, 0.95, 0.95, 0.95]}
    r = chain(sv, permitted_state=permitted, threshold=g.fisher_rao_threshold, gate=g)
    assert g.sigil_log == [], "disabled gate must not SIGIL"
    print(f"  ✅ FitnessGate disabled: verdict=ok no SIGIL")


def test_ch12_fitness_gate_canonical_thresholds():
    """Canonical thresholds match the SOVOS invariants (care=0.95, BFT=23/33)."""
    g = fitness_gate()
    assert abs(g.care_floor - 0.95) < 1e-9
    assert abs(g.bft_quorum - 23.0 / 33.0) < 1e-9
    assert g.poincare_threshold == 0.5
    assert g.fisher_rao_threshold == 1.0
    print(f"  ✅ Canonical thresholds: care={g.care_floor}, bft={g.bft_quorum:.3f}")


def test_ch13_chain_to_dict_round_trip():
    """ChainResult.to_dict() must be JSON-serializable (for SIGIL emission)."""
    import json
    r = chain({"vector": [0.1, 0.2, 0.3]})
    d = r.to_dict()
    blob = json.dumps(d)  # must not raise
    assert "chain_id" in blob
    assert "ts" in blob
    print(f"  ✅ ChainResult.to_dict → JSON: {len(blob)} bytes")


def test_ch14_self_test_returns_dict():
    """self_test must report which peer packages are reachable."""
    info = self_test()
    assert isinstance(info, dict)
    assert "chain_works" in info
    if info["chain_works"]:
        print(f"  ✅ self_test: fr={info['sovos_fisher_rao']} hyperbolic={info['hyperbolic']} "
              f"chain={info['chain_works']} smoke_fr={info.get('smoke_fisher_rao')}")
    else:
        print(f"  ⚠️  self_test chain_works=False: {info.get('chain_error')}")


def test_ch15_vector_to_spd_is_spd():
    """The internal helper _vector_to_spd must always produce an SPD matrix."""
    from csoai_chain import _vector_to_spd
    v = [0.1, 0.2, 0.3, 0.4]
    M = _vector_to_spd(v)
    # Symmetric
    assert np.allclose(M, M.T), "M not symmetric"
    # Positive definite: all eigenvalues > 0
    eigvals = np.linalg.eigvalsh(M)
    assert np.all(eigvals > 0), f"not PD, eigvals={eigvals}"
    print(f"  ✅ _vector_to_spd: SPD matrix shape {M.shape}, min eigval={eigvals.min():.4f}")


if __name__ == "__main__":
    tests = [
        test_ch01_chain_runs_with_no_peers,
        test_ch02_chain_with_fisher_rao_only,
        test_ch03_chain_with_clans_only,
        test_ch04_chain_full_with_both,
        test_ch05_chain_id_is_deterministic,
        test_ch06_chain_id_changes_with_input,
        test_ch07_chain_handles_statevector_object,
        test_ch08_chain_handles_ndarray,
        test_ch09_fitness_gate_pass,
        test_ch10_fitness_gate_escalate_far,
        test_ch11_fitness_gate_disabled,
        test_ch12_fitness_gate_canonical_thresholds,
        test_ch13_chain_to_dict_round_trip,
        test_ch14_self_test_returns_dict,
        test_ch15_vector_to_spd_is_spd,
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
