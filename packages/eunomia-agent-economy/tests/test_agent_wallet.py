#!/usr/bin/env python3
"""test_agent_wallet — eunomia agent economy."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_agent_economy.agent_wallet import AgentWallet


def test_npc_can_participate():
    a = AgentWallet("dragon")
    a.mint_sbt("Watchdog Level 5", 5)
    a.fund(1000); a.stake_to_quote(200); a.record_trade(0.95)
    assert a.can_participate() is True
    assert a.reputation >= 0.2


def test_no_stake_no_participate():
    a = AgentWallet("novice")
    a.fund(100)
    assert a.can_participate() is False  # no stake


def test_exploit_slashes():
    a = AgentWallet("rogue")
    a.fund(500); a.stake_to_quote(300)
    burned = a.record_trade(0, exploit=True)
    assert burned == 150.0  # 50% stake burn
    assert a.reputation == 0.0


if __name__ == "__main__":
    test_npc_can_participate(); print("ok: npc can participate")
    test_no_stake_no_participate(); print("ok: no stake no participate")
    test_exploit_slashes(); print("ok: exploit slashes")
    print("ALL AGENT ECONOMY TESTS PASS")
