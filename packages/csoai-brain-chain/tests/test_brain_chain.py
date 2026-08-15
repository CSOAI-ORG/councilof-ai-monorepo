"""Test the csoai-brain-chain integration seam (master gap #2 wired).

Verifies: brain vector → chain → fitness gate verdict → signed record, plus the
VWM named residence, plus the graceful never-fabricate path.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import csoai_brain_chain as bc

# --- a minimal fake brain (implements a to_vector surface) ---
class FakeBrain:
    def __init__(self, vec):
        self._vec = vec
    def to_vector(self, task=None):
        return self._vec

class FakeChainResult:
    chain_id = "test-chain-abc"
    fisher_rao_distance = 0.0845
    poincare_distance = 0.5
    passed = True

# monkeypatch the module's chain access for the deterministic test
def test_vwm_surface():
    v = bc.VWMSurface()
    assert v.name == "vwm"
    assert v.estimate_depth({"img": 1}) is None   # no model → None, honest
    assert v.predict_world({"s": 1}) is None
    print("  [ok] VWM surface has a real named home")

def test_no_chain_no_fabrication():
    r = bc.run_brain_through_chain(None, task=None)  # brain None
    assert r.verdict in ("UNMEASURED", "UNKNOWN"), f"got {r.verdict}"
    # even without inputs it must return a deterministic signature, never lie
    assert r.signature
    print(f"  [ok] no-brain -> {r.verdict} (never fabricated)")

def test_vector_from_brain():
    brain = FakeBrain([0.1, 0.2, 0.3, 0.4])
    r = bc.run_brain_through_chain(brain, task="t")
    # vector extracted
    assert abs(r.vector[0] - 0.1) < 1e-6
    # signature computed deterministically
    s1 = r.signed_fingerprint()
    s2 = r.signed_fingerprint()
    assert s1 == s2
    print(f"  [ok] brain vector extracted + deterministic signature {s1[:12]}...")

def test_chain_wire_monkeypatched():
    # Simulate a present sovos-chain by injecting a ChainResult provider.
    orig = bc._sovos_chain
    class FakeChainMod:
        def chain(self, *a, **k):
            return FakeChainResult()
        class FitnessGate:
            def __init__(self, care_floor=0.95, bft_quorum=23/33):
                self.care_floor = care_floor; self.bft_quorum = bft_quorum
            def evaluate(self, v): return FakeVerdict()
    class FakeVerdict:
        def __str__(self): return "PASS"
    bc._sovos_chain = FakeChainMod()
    try:
        brain = FakeBrain([0.2, 0.4, 0.6, 0.8])
        gate = bc._sovos_chain.FitnessGate()
        r = bc.run_brain_through_chain(brain, task="x", gate=gate)
        assert r.chain_id == "test-chain-abc"
        assert r.verdict == "PASS"
        assert abs(r.fisher_rao_distance - 0.0845) < 1e-6
        print(f"  [ok] brain -> chain -> gate -> signed (chain_id {r.chain_id}, verdict {r.verdict})")
    finally:
        bc._sovos_chain = orig

if __name__ == "__main__":
    print("csoai-brain-chain seam tests:")
    test_vwm_surface()
    test_no_chain_no_fabrication()
    test_vector_from_brain()
    test_chain_wire_monkeypatched()
    print("\nALL PASS")