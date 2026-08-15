"""Tests for the SOVOS OOWM layer (no API key, no network)."""
from csoai_core.owm import (
    DreamDepth,
    OWMRouter,
    NemotronOWM,
    OWMState,
    _select_best_future,
    governed_score,
)


def _state(g: float = 0.95, s: float = 0.91) -> OWMState:
    return OWMState(
        epoch=48291,
        scale=8,
        active_nodes=[
            {"id": "kimi_k3_adapter", "type": "model", "g": 0.95, "energy": 150.0},
            {"id": "csoai_governance", "type": "clan", "g": 0.98, "energy": 80.0},
        ],
        recent_events=[
            {"timestamp": "14:02:00", "type": "mcp_call", "summary": "water check passed"},
        ],
        gspc_current={"G": g, "S": s, "P": 1.0, "C": 0.88},
        pending_tasks=["security_audit_cycle"],
    )


def test_owm_no_key_returns_fallback():
    owm = NemotronOWM(api_key="")
    assert owm.available is False
    futures = owm.dream(_state(), deep=True)
    assert len(futures) == 1
    assert futures[0].scenario_id == "fallback_no_key"
    assert futures[0].probability == 1.0


def test_dream_quota_triggers_fallback():
    owm = NemotronOWM(api_key="sk-or-test", max_free=1)
    assert owm.available is True
    # First call would hit network; instead simulate quota without key by
    # pre-setting the counter past the limit.
    owm.dream_count = owm.max_free_dreams
    futures = owm.dream(_state())
    assert futures[0].scenario_id == "fallback_quota"


def test_router_route_logic():
    router = OWMRouter()
    # Governance below threshold -> CRITICAL (deep Nemotron)
    assert router.route(_state(g=0.70), urgency=0.3, importance=0.5) == DreamDepth.CRITICAL
    # High importance, low urgency -> DEEP
    assert router.route(_state(), urgency=0.2, importance=0.9) == DreamDepth.DEEP
    # Medium importance -> FAST
    assert router.route(_state(), urgency=0.3, importance=0.6) == DreamDepth.FAST
    # Low -> INSTINCT
    assert router.route(_state(), urgency=0.3, importance=0.3) == DreamDepth.INSTINCT


def test_router_select_action_local_paths():
    router = OWMRouter()
    # Customer/revenue task, healthy state -> FAST local dream, allowed.
    result = router.select_action(_state(), task="customer report for revenue")
    assert result["action"] != "BLOCKED"
    assert result["depth"] == DreamDepth.FAST.value

    # Instinct path
    result = router.select_action(_state(), task="maintain")
    assert result["depth"] == DreamDepth.INSTINCT.value


def test_g_block_escalates_to_human():
    router = OWMRouter()
    # Very low G -> route() returns CRITICAL, but the fallback G stays low
    # (no API key), so the G-block must trigger and escalate to human.
    low = _state(g=0.10)
    result = router.select_action(low, task="routine")
    # With no API key the CRITICAL depth falls back to local whose G is
    # whatever the state says (0.10) -> must BLOCK + escalate.
    assert result["action"] == "BLOCKED"
    assert result["fallback"] == "ESCALATE_TO_HUMAN"


def test_select_best_future_weights_g():
    futures = [
        type("F", (), {"gspc": {"G": 0.9, "S": 0.9, "P": 0.9, "C": 0.9}, "scenario_id": "a"})(),
        type("F", (), {"gspc": {"G": 1.0, "S": 0.1, "P": 0.1, "C": 0.1}, "scenario_id": "b"})(),
    ]
    best = _select_best_future(futures)
    # G 40%: b = 0.4 + 0.03 + 0.02 + 0.01 = 0.46; a = 0.36+0.27+0.18+0.09 = 0.90
    assert best.scenario_id == "a"


def test_governed_score_stamps_state():
    result = governed_score(_state())
    report = result.report()
    assert "G" in report and "composite" in report
