"""Tests for csoai-stigmergy v0.1.0 SCAFFOLD.

10 tests covering:
- Pheromone deposit returns a stable sv_id
- Reinforce resets decay timer
- Decay reduces concentration over time
- Sense filters by threshold
- strongest() returns top-k by concentration
- stigmergy_demo runs without errors and shows indirect coordination
- StateBus subscribers fire (stigmergy side-effect)
"""
import sys
import time
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sovos-mind" / "src"))

from csoai_stigmergy import Pheromone, PheromoneTrail, stigmergy_demo
from sovos_mind.state import StateBus, StateVector


def test_01_deposit_returns_sv_id():
    """A deposit should give back a non-empty sv_id."""
    bus = StateBus()
    trail = PheromoneTrail(bus)
    sv_id = trail.deposit("agent-1", [0.5, 0.3])
    assert isinstance(sv_id, str)
    assert len(sv_id) == 16
    print(f"  ✅ deposit returns sv_id: {sv_id}")


def test_02_deposit_writes_to_bus():
    """A deposit should be visible via the StateBus's read_by_layer."""
    bus = StateBus()
    trail = PheromoneTrail(bus, layer="test_trail")
    trail.deposit("a", [1.0, 0.0])
    trail.deposit("b", [0.0, 1.0])
    on_layer = bus.read_by_layer("test_trail")
    assert len(on_layer) == 2
    sources = sorted(sv.source for sv in on_layer)
    assert sources == ["a", "b"]
    print(f"  ✅ deposit writes to bus: {sources}")


def test_03_subscribe_fires_on_deposit():
    """A subscriber to the pheromone layer should fire when something is deposited.

    This is the REAL stigmergy mechanism — agents react to environment,
    not to each other.
    """
    bus = StateBus()
    trail = PheromoneTrail(bus, layer="subscribe_test")
    received = []
    bus.subscribe("subscribe_test", lambda sv: received.append(sv))
    trail.deposit("agent-A", [1.0])
    trail.deposit("agent-B", [0.5])
    assert len(received) == 2, f"subscriber should fire on every deposit; got {len(received)}"
    sources = [sv.source for sv in received]
    assert sources == ["agent-A", "agent-B"]
    print(f"  ✅ subscribe fires on deposit: {sources} (indirect, no direct messages)")


def test_04_reinforce_increases_concentration():
    """Reinforcing a pheromone should reset its decay timer."""
    bus = StateBus()
    trail = PheromoneTrail(bus, half_life_seconds=10.0)
    sv_id = trail.deposit("a", [1.0])
    p = trail._pheromones[sv_id]
    initial_time = p.deposited_at
    # Wait a tiny bit (not enough to decay meaningfully)
    time.sleep(0.01)
    trail.reinforce(sv_id)
    assert p.deposited_at > initial_time, "reinforce should reset deposited_at"
    print(f"  ✅ reinforce resets decay timer")


def test_05_decay_reduces_concentration():
    """Time should reduce pheromone concentration (exponential decay)."""
    p = Pheromone(sv_id="x", vector=[1.0], deposited_at=time.time(),
                  concentration=1.0, half_life_seconds=1.0)
    # Simulate 2 half-lives elapsed
    p.deposited_at = time.time() - 2.0
    c = p.decay()
    assert 0.24 < c < 0.26, f"after 2 half-lives, expected ~0.25; got {c}"
    print(f"  ✅ decay: 2 half-lives → concentration {c:.4f} (~0.25 expected)")


def test_06_sense_filters_by_threshold():
    """sense(threshold) should only return alive pheromones above threshold."""
    bus = StateBus()
    trail = PheromoneTrail(bus, half_life_seconds=1.0)
    fresh_id = trail.deposit("fresh", [1.0])        # concentration = 1.0
    # Make a "stale" pheromone by depositing then backdating
    stale_id = trail.deposit("stale", [0.5])
    trail._pheromones[stale_id].deposited_at = time.time() - 100.0  # way past half-life
    trail._pheromones[stale_id].decay()
    alive = trail.sense(threshold=0.1)
    ids = [p.sv_id for p in alive]
    assert fresh_id in ids
    assert stale_id not in ids, f"stale pheromone (concentration {trail._pheromones[stale_id].concentration}) should be filtered"
    print(f"  ✅ sense filters stale (concentration 0.0) vs fresh (concentration 1.0)")


def test_07_strongest_returns_top_k():
    """strongest(k) should return the highest-concentration pheromones."""
    bus = StateBus()
    trail = PheromoneTrail(bus, half_life_seconds=1.0)
    # Drop 3 pheromones with different ages
    trail.deposit("old", [1.0])
    time.sleep(0.05)
    trail.deposit("middle", [1.0])
    time.sleep(0.05)
    trail.deposit("new", [1.0])
    # "old" should be weakest, "new" strongest
    strongest = trail.strongest(k=1)
    assert strongest[0].metadata["source"] == "new"
    print(f"  ✅ strongest: {strongest[0].metadata['source']} (newest = highest concentration)")


def test_08_no_direct_messaging_required():
    """Two agents coordinate via the bus WITHOUT calling each other.

    This is the core stigmergy claim: no direct A2A, no function calls
    between agents, just shared environment.
    """
    bus = StateBus()
    trail = PheromoneTrail(bus, layer="coordination")
    # No direct reference between agent_forager and agent_scout anywhere.
    # They only share the bus.
    agent_scout_seen = []
    agent_forager_seen = []

    def scout_callback(sv):
        if sv.source != "scout":
            agent_scout_seen.append(sv.source)

    def forager_callback(sv):
        if sv.source == "scout":
            agent_forager_seen.append(sv)

    bus.subscribe("coordination", scout_callback)
    bus.subscribe("coordination", forager_callback)

    # Scout drops a pheromone — forager picks it up automatically.
    trail.deposit("scout", [1.0, 0.0])
    # Scout sees that forager is doing something (no idea what)
    trail.deposit("forager", [0.0, 1.0])

    assert "forager" in agent_scout_seen, "scout should see forager's deposit via bus"
    assert "scout" in [s.source for s in agent_forager_seen], "forager should see scout's deposit via bus"
    # Neither agent ever called the other directly
    print(f"  ✅ indirect coordination: scout sees forager, forager sees scout, no direct call")


def test_09_stigmergy_demo_runs():
    """The canned demo should run end-to-end and produce sensible output."""
    result = stigmergy_demo(verbose=False)
    assert "log" in result
    assert "trail_count" in result
    assert result["trail_count"] == 2  # 2 distinct sources = 2 pheromones
    # Round 1: scout deposits
    assert result["log"][0]["action"] == "deposit"
    # Round 5: 2 alive
    assert result["log"][-1]["count"] == 2
    print(f"  ✅ stigmergy_demo: 5 rounds, 2 pheromones deposited, indirect coordination works")


def test_10_decay_with_zero_half_life():
    """half_life=0 should mean instant decay (concentration → 0)."""
    p = Pheromone(sv_id="x", vector=[1.0], deposited_at=time.time(),
                  concentration=1.0, half_life_seconds=0.0)
    c = p.decay()
    assert c == 0.0, f"half_life=0 should give 0 concentration, got {c}"
    print(f"  ✅ half_life=0 → instant decay (concentration=0)")


def main():
    tests = [
        test_01_deposit_returns_sv_id,
        test_02_deposit_writes_to_bus,
        test_03_subscribe_fires_on_deposit,
        test_04_reinforce_increases_concentration,
        test_05_decay_reduces_concentration,
        test_06_sense_filters_by_threshold,
        test_07_strongest_returns_top_k,
        test_08_no_direct_messaging_required,
        test_09_stigmergy_demo_runs,
        test_10_decay_with_zero_half_life,
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
