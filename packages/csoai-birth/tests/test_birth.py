"""Tests for csoai_birth — Mode 0 birth encoder."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np

from csoai_birth import BirthEncoder, BirthResult, birth, encoder, self_test


def test_b01_deterministic():
    """Same user_id → same coordinate (replay-safe)."""
    be = BirthEncoder(namespace="t")
    a = be.encode("alice", "Alice")
    b = be.encode("alice", "Alice")
    assert a.coordinate == b.coordinate, "birth not deterministic"
    assert a.chain_id == b.chain_id
    print(f"  ✅ deterministic: same user → same coord + same chain_id")


def test_b02_distinct_users_distinct():
    """Different user_ids → different coordinates."""
    be = BirthEncoder(namespace="t")
    a = be.encode("alice")
    b = be.encode("bob")
    assert a.coordinate != b.coordinate
    assert a.chain_id != b.chain_id
    print(f"  ✅ distinct users → distinct coords")


def test_b03_coordinate_inside_ball():
    """The coordinate must be inside the Poincaré ball (norm < 1)."""
    be = BirthEncoder(namespace="t", radius=0.85)
    for uid in ("alice", "bob", "carol", "dave", "eve", "frank"):
        r = be.encode(uid)
        assert r.coordinate_norm < 1.0, f"{uid}: norm={r.coordinate_norm}"
        assert r.coordinate_norm <= 0.85 + 1e-9, f"{uid}: norm={r.coordinate_norm}"
        assert all(-1.0 < c < 1.0 for c in r.coordinate)
    print(f"  ✅ 6 users, all in ball (norm ≤ 0.85)")


def test_b04_coordinate_dim():
    """The coordinate has the configured dimension."""
    be = BirthEncoder(namespace="t", dim=4)
    r = be.encode("alice")
    assert len(r.coordinate) == 4
    be8 = BirthEncoder(namespace="t", dim=8)
    r8 = be8.encode("alice")
    assert len(r8.coordinate) == 8
    print(f"  ✅ dim config: 4 → 4, 8 → 8")


def test_b05_chain_id_audit():
    """chain_id is a 24-char hex hash, deterministic, unique per user."""
    be = BirthEncoder(namespace="t")
    a = be.encode("alice")
    assert len(a.chain_id) == 24
    assert all(c in "0123456789abcdef" for c in a.chain_id)
    b = be.encode("bob")
    assert a.chain_id != b.chain_id
    print(f"  ✅ chain_id is 24-char hex, unique per user")


def test_b06_namespace_separates_users():
    """Same user_id in different namespaces → different coordinates."""
    a = BirthEncoder(namespace="ns1").encode("alice")
    b = BirthEncoder(namespace="ns2").encode("alice")
    assert a.coordinate != b.coordinate
    print(f"  ✅ namespace isolation: alice@ns1 ≠ alice@ns2")


def test_b07_bus_vector_payload():
    """The birth result can be fed directly to a StateBus as a vector."""
    be = BirthEncoder(namespace="iokfarm")
    r = be.encode("alice", "Alice", extra={"tier": "pro"})
    v = r.to_bus_vector()
    assert v["source"] == "birth:iokfarm"
    assert v["layer"] == "water"
    assert v["vector"] == r.coordinate
    assert v["payload"]["user_id"] == "alice"
    assert v["payload"]["display_name"] == "Alice"
    assert v["payload"]["extra"]["tier"] == "pro"
    assert v["payload"]["chain_id"] == r.chain_id
    print(f"  ✅ bus vector payload: source=birth:iokfarm, layer=water, extra preserved")


def test_b08_top_level_birth_function():
    """The module-level `birth()` function works as a one-liner."""
    r = birth("alice", "Alice", namespace="t")
    assert r.user_id == "alice"
    assert r.display_name == "Alice"
    assert r.namespace == "t"
    assert r.coordinate_norm < 1.0
    print(f"  ✅ top-level birth() one-liner works")


def test_b09_encoder_singleton_per_namespace():
    """encoder(ns) returns the same instance per namespace."""
    a = encoder("ns1")
    b = encoder("ns1")
    c = encoder("ns2")
    assert a is b
    assert a is not c
    print(f"  ✅ encoder() is singleton per namespace")


def test_b10_self_test():
    """self_test() returns a complete picture."""
    info = self_test()
    assert info["deterministic"] is True
    assert info["different_users_distinct"] is True
    assert info["coordinate_inside_ball"] is True
    assert info["chain_id_len"] == 24
    print(f"  ✅ self_test: {info}")


def test_b11_invalid_radius_raises():
    """radius >= 1 or <= 0 must raise ValueError."""
    try:
        BirthEncoder(namespace="t", radius=1.5)
        assert False, "should have raised"
    except ValueError as e:
        assert "radius" in str(e).lower()
    try:
        BirthEncoder(namespace="t", radius=0.0)
        assert False, "should have raised"
    except ValueError as e:
        assert "radius" in str(e).lower()
    print(f"  ✅ radius validation: out-of-range raises ValueError")


def test_b12_invalid_dim_raises():
    """dim < 2 must raise ValueError."""
    try:
        BirthEncoder(namespace="t", dim=1)
        assert False, "should have raised"
    except ValueError:
        pass
    print(f"  ✅ dim validation: dim=1 raises ValueError")


def test_b13_box_muller_distribution():
    """Box-Muller expansion produces non-trivial variation."""
    be = BirthEncoder(namespace="boxmuller", dim=8, radius=0.85)
    coords = [be.encode(f"user_{i:04d}").coordinate for i in range(20)]
    arr = np.array(coords)
    # Each dim should have non-trivial variance (not all the same value)
    stds = arr.std(axis=0)
    assert all(s > 0.01 for s in stds), f"dims too uniform: {stds}"
    print(f"  ✅ Box-Muller variance: stds={[f'{s:.3f}' for s in stds]}")


if __name__ == "__main__":
    tests = [
        test_b01_deterministic,
        test_b02_distinct_users_distinct,
        test_b03_coordinate_inside_ball,
        test_b04_coordinate_dim,
        test_b05_chain_id_audit,
        test_b06_namespace_separates_users,
        test_b07_bus_vector_payload,
        test_b08_top_level_birth_function,
        test_b09_encoder_singleton_per_namespace,
        test_b10_self_test,
        test_b11_invalid_radius_raises,
        test_b12_invalid_dim_raises,
        test_b13_box_muller_distribution,
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
