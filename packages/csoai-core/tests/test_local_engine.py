"""Tests for the local inference engine (no live network required)."""
from csoai_core.local_engine import OllamaEngine
from csoai_core.owm import OWMRouter, OWMState, DreamDepth


class _FakeEngine:
    """Duck-typed stand-in for OllamaEngine that avoids any real call."""

    def __init__(self, model="fake", responses=None):
        self.model = model
        self.responses = responses or {"r": "GOVERNED"}
        self.calls = 0

    def list_models(self):
        return [self.model]

    def has_model(self, name=None):
        return (name or self.model) in [self.model]

    def dream(self, prompt, state=None, **kwargs):
        self.calls += 1
        from csoai_core.owm import DreamOutcome
        gspc = dict(state.gspc_current) if state else {"G": 0.9, "S": 0.9, "P": 0.9, "C": 0.9}
        return DreamOutcome(
            scenario_id="fast_local",
            description=self.responses.get("r", "GOVERNED"),
            probability=1.0,
            gspc=gspc,
            recommended_action="CONTINUE",
            risk_level="LOW",
        )


def _state() -> OWMState:
    return OWMState(
        epoch=1, scale=4,
        active_nodes=[{"id": "a", "type": "agent", "g": 0.95, "energy": 10.0}],
        recent_events=[],
        gspc_current={"G": 0.95, "S": 0.91, "P": 1.0, "C": 0.88},
        pending_tasks=[],
    )


def test_router_uses_injected_local_engine_for_fast():
    engine = _FakeEngine()
    router = OWMRouter(local_engine=engine)
    result = router.select_action(_state(), task="customer report for revenue")
    assert result["depth"] == DreamDepth.FAST.value
    assert engine.calls == 1
    assert result["scenario_id"] == "fast_local"
    assert result["action"] == "CONTINUE"


def test_router_falls_back_when_engine_raises():
    class _Broken:
        def dream(self, *a, **k):
            raise RuntimeError("offline")

    router = OWMRouter(local_engine=_Broken())
    result = router.select_action(_state(), task="customer report for revenue")
    # Falls back to fast_local stub, still governed, not blocked.
    assert result["action"] != "BLOCKED"
    assert result["depth"] == DreamDepth.FAST.value


def test_ollama_engine_construction():
    e = OllamaEngine(host="localhost:11434", ssh_host="sov-brain-2", model="qwen2.5:1.5b")
    assert e.ssh_host == "sov-brain-2"
    assert e.model == "qwen2.5:1.5b"
