"""Tests for csoai_bus_redis — Redis-backed SOVOS StateBus."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_bus_redis import RedisBus, StateVector, self_test


def test_br01_basic_append_and_read():
    """Append two vectors, read them back by layer.

    NB: LPUSH prepends, so the most-recent vector comes first.
    Use a set comparison instead of positional indexing.
    """
    bus = RedisBus(use_fakeredis=True)
    sv1 = StateVector(source="test", layer="water", vector=[1.0, 2.0])
    sv2 = StateVector(source="test", layer="water", vector=[3.0, 4.0])
    bus.append(sv1)
    bus.append(sv2)
    water = bus.read_by_layer("water")
    assert len(water) == 2
    ids = {v.sv_id for v in water}
    assert sv1.sv_id in ids and sv2.sv_id in ids
    vectors = {tuple(v.vector) for v in water}
    assert (1.0, 2.0) in vectors and (3.0, 4.0) in vectors
    print(f"  ✅ append + read_by_layer: 2 vectors, IDs both present")
    bus.close()


def test_br02_read_by_source():
    """Append from two sources; read by each."""
    bus = RedisBus(use_fakeredis=True)
    bus.append(StateVector(source="a", layer="water", vector=[1.0]))
    bus.append(StateVector(source="b", layer="water", vector=[2.0]))
    bus.append(StateVector(source="a", layer="milk", vector=[3.0]))
    a = bus.read_by_source("a")
    b = bus.read_by_source("b")
    assert len(a) == 2
    assert len(b) == 1
    assert all(sv.source == "a" for sv in a)
    print(f"  ✅ read_by_source: a={len(a)}, b={len(b)}")
    bus.close()


def test_br03_in_process_subscribe():
    """Subscribe fires on append (in-process, fakeredis path)."""
    bus = RedisBus(use_fakeredis=True)
    received = []
    bus.subscribe("water", lambda sv: received.append(sv))
    bus.append(StateVector(source="x", layer="water", vector=[1.0]))
    bus.append(StateVector(source="x", layer="water", vector=[2.0]))
    # fakeredis fires both in-process AND pub/sub; at least one callback fired
    assert len(received) >= 1, f"subscriber should have fired: {received}"
    print(f"  ✅ subscribe fired {len(received)}× (in-process callback works)")
    bus.close()


def test_br04_layer_isolation():
    """Different layers are isolated."""
    bus = RedisBus(use_fakeredis=True)
    bus.append(StateVector(source="x", layer="water", vector=[1.0]))
    bus.append(StateVector(source="x", layer="milk", vector=[2.0]))
    bus.append(StateVector(source="x", layer="honey", vector=[3.0]))
    assert len(bus.read_by_layer("water")) == 1
    assert len(bus.read_by_layer("milk")) == 1
    assert len(bus.read_by_layer("honey")) == 1
    assert len(bus.read_by_layer("action")) == 0
    print(f"  ✅ layer isolation: water/milk/honey each have 1, action=0")
    bus.close()


def test_br05_payload_roundtrip():
    """Payload dict survives Redis serialization."""
    bus = RedisBus(use_fakeredis=True)
    payload = {"user": "alice", "tier": "pro", "meta": [1, 2, 3]}
    sv = StateVector(source="x", layer="water", vector=[1.0], payload=payload)
    bus.append(sv)
    got = bus.read_by_layer("water")[0]
    assert got.payload == payload, f"payload mismatch: {got.payload}"
    print(f"  ✅ payload roundtrip: {payload}")


def test_br06_mint_sv_id_when_empty():
    """An sv without sv_id gets one minted from its content hash."""
    bus = RedisBus(use_fakeredis=True)
    sv = StateVector(source="x", layer="water", vector=[1.0])
    assert sv.sv_id == ""
    bus.append(sv)
    assert sv.sv_id and len(sv.sv_id) == 16
    print(f"  ✅ minted sv_id: {sv.sv_id}")


def test_br07_stats():
    """stats() returns sensible counts."""
    bus = RedisBus(use_fakeredis=True)
    for i in range(5):
        bus.append(StateVector(source="s1", layer="water", vector=[float(i)]))
    for i in range(3):
        bus.append(StateVector(source="s1", layer="milk", vector=[float(i)]))
    s = bus.stats()
    assert s["by_layer"]["water"] == 5
    assert s["by_layer"]["milk"] == 3
    assert s["total"] == 8
    assert s["backend"] == "fakeredis"
    print(f"  ✅ stats: water=5, milk=3, total=8, backend={s['backend']}")


def test_br08_namespace_isolation():
    """Two buses with different namespaces don't see each other's data."""
    b1 = RedisBus(use_fakeredis=True, namespace="bus1")
    b2 = RedisBus(use_fakeredis=True, namespace="bus2")
    b1.append(StateVector(source="x", layer="water", vector=[1.0]))
    assert len(b1.read_by_layer("water")) == 1
    assert len(b2.read_by_layer("water")) == 0
    print(f"  ✅ namespace isolation: bus1 has data, bus2 empty")
    b1.close(); b2.close()


def test_br09_self_test_helper():
    """The self_test() helper returns a complete picture."""
    result = self_test()
    assert result["appended_ok"] is True
    assert result["subscribers_fired"] >= 1
    assert result["stats_total"] == 2
    assert result["backend"] == "fakeredis"
    print(f"  ✅ self_test: {result}")


def test_br10_close_is_clean():
    """close() stops the listener thread without error."""
    bus = RedisBus(use_fakeredis=True)
    bus.subscribe("water", lambda sv: None)
    bus.append(StateVector(source="x", layer="water", vector=[1.0]))
    bus.close()  # should not raise
    print(f"  ✅ close() clean shutdown")


if __name__ == "__main__":
    tests = [
        test_br01_basic_append_and_read,
        test_br02_read_by_source,
        test_br03_in_process_subscribe,
        test_br04_layer_isolation,
        test_br05_payload_roundtrip,
        test_br06_mint_sv_id_when_empty,
        test_br07_stats,
        test_br08_namespace_isolation,
        test_br09_self_test_helper,
        test_br10_close_is_clean,
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
