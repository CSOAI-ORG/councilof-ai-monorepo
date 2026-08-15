"""Tests for csoai-hive — the Python facade of the Fractal Monotric Hive."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_hive import (
    Scale, GSPCAxes, HiveNode, NodeState,
    WITHDRAWN_MODELS, owem_swarm, jspace_deck,
    describe_scale, self_test,
)


def test_h01_scales_distinct():
    scales = {Scale.TOKEN, Scale.AGENT, Scale.CLAN, Scale.CLUSTER, Scale.ECOSYSTEM}
    assert len(scales) == 5
    print("  PASS h01 scales distinct")


def test_h02_describe_scale():
    for s, name in [(0, "TOKEN"), (8, "AGENT"), (16, "CLAN"),
                    (24, "CLUSTER"), (32, "ECOSYSTEM")]:
        out = describe_scale(s)
        assert name in out, f"describe_scale({s}) missing {name}: got {out!r}"
    print("  PASS h02 describe_scale naming")


def test_h03_gspc_axes_array():
    a = GSPCAxes(governance=0.8, security=0.9, privacy=0.7, commerce=0.6)
    assert a.as_array() == [0.8, 0.9, 0.7, 0.6]
    b = GSPCAxes.from_array([0.1, 0.2, 0.3, 0.4])
    assert (b.governance, b.security, b.privacy, b.commerce) == (0.1, 0.2, 0.3, 0.4)
    print("  PASS h03 GSPCAxes round-trip")


def test_h04_gspc_axes_validation():
    try:
        GSPCAxes.from_array([0.1, 0.2])
        assert False, "should have raised"
    except ValueError:
        pass
    print("  PASS h04 from_array len-check")


def test_h05_withdrawn_registry_present():
    assert len(WITHDRAWN_MODELS) >= 4
    print(f"  PASS h05 WITHDRAWN_MODELS loaded: {len(WITHDRAWN_MODELS)} entries")


def test_h06_owem_swarm_loads():
    swarm = owem_swarm()
    if not swarm.clans:
        print("  SKIP h06 OWEM clan file not present")
        return
    assert swarm.swarm_id.startswith("owem-"), swarm.swarm_id
    assert len(swarm.active_clans) > 0
    # check clan-mastra specifically
    mastra = swarm.clan_for("agent_routing")
    assert mastra is not None
    assert mastra.framework == "mastra"
    print(f"  PASS h06 OWEM swarm: {len(swarm.clans)} clans, "
          f"{len(swarm.active_clans)} active")


def test_h07_jspace_deck_loads():
    deck = jspace_deck()
    assert len(deck.cards) >= 50, f"expected 54, got {len(deck.cards)}"
    c0 = deck.cards[0]
    assert c0.card_id
    assert c0.axis
    print(f"  PASS h07 J-Space deck: {len(deck.cards)} cards")


def test_h08_hive_node_fractal():
    g = GSPCAxes(0.5, 0.5, 0.5, 0.5)
    for scale in [Scale.TOKEN, Scale.AGENT, Scale.CLAN, Scale.CLUSTER, Scale.ECOSYSTEM]:
        n = HiveNode(id=1, epoch=0, scale=scale, axes=g,
                     state=NodeState(energy=0.5, gspc=g, kind="Token",
                                     is_dreaming=False, last_action="init",
                                     memory=[]),
                     label="test")
        assert n.scale == scale
        assert n.is_root
    print("  PASS h08 HiveNode fractal: same struct at every scale")


def test_h09_hive_node_withdrawn_label():
    g = GSPCAxes(0.1, 0.1, 0.1, 0.1)
    n = HiveNode(id=2, epoch=0, scale=Scale.AGENT, axes=g,
                 state=NodeState(energy=0.0, gspc=g, kind="Agent",
                                 is_dreaming=False, last_action="", memory=[]),
                 label="claude-opus-4.5-haunted")
    assert n.is_withdrawn("claude-opus-4.5-haunted")
    assert not n.is_withdrawn("nonexistent-model")
    print("  PASS h09 HiveNode.is_withdrawn consults registry")


def test_h10_self_test_smoke():
    st = self_test()
    assert "scales" in st
    assert "n_withdrawn" in st
    assert "rust_kernel_loaded" in st
    assert st["n_jspace_cards"] >= 50
    assert st["n_active_clans"] >= 1
    print(f"  PASS h10 self_test: rust={st['rust_kernel_loaded']}, "
          f"cards={st['n_jspace_cards']}, clans={st['n_active_clans']}")


def main():
    tests = [
        test_h01_scales_distinct,
        test_h02_describe_scale,
        test_h03_gspc_axes_array,
        test_h04_gspc_axes_validation,
        test_h05_withdrawn_registry_present,
        test_h06_owem_swarm_loads,
        test_h07_jspace_deck_loads,
        test_h08_hive_node_fractal,
        test_h09_hive_node_withdrawn_label,
        test_h10_self_test_smoke,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{'OK' if passed == len(tests) else 'PARTIAL'} "
          f"{passed}/{len(tests)} PASSED")


if __name__ == "__main__":
    main()
