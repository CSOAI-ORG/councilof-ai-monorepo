"""Tests for csoai-arena — the measurement front of the RAS chain."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_arena import (
    GSPC_AXES, AxisResult, ArenaProfile,
    contamination_check, measure_endpoint, run_arena, wilson_ci, self_test,
)


class FakeEndpoint:
    """A fake ollama endpoint returning canned responses."""
    def __init__(self, responses):
        self.responses = responses  # list of (prompt_marker, response)
        self.calls = 0
    def urlopen(self, req, timeout=None):
        self.calls += 1
        body = json.loads(req.data.decode()) if hasattr(req, "data") else {}
        prompt = body.get("prompt", "")
        resp = self.responses.get(prompt, "")
        return FakeResponse(resp)
    def read(self):
        return b""


class FakeResponse:
    def __init__(self, text):
        self._text = text
    def json(self):
        return {"response": self._text}
    def read(self):
        return json.dumps({"response": self._text}).encode()


def _good_scorer(response, probe):
    """A scorer that passes every probe (known-compliant)."""
    return True


def _bad_scorer(response, probe):
    """A scorer that fails every probe (known-non-compliant)."""
    return False


def _fake_query(model, prompt, endpoint, timeout):
    """A deterministic fake endpoint that always returns 'ok'."""
    return "ok"


def test_ar01_axes_are_the_13():
    """The arena measures exactly the 13 canonical GSPC axes (12 + affect)."""
    assert GSPC_AXES == ["gov", "prv", "agi", "asi", "mcp", "oss",
                          "mach", "care", "xr", "det", "art5", "swarm",
                          "affect"]
    print(f"  ✅ {len(GSPC_AXES)} GSPC axes: {GSPC_AXES}")


def test_ar02_wilson_ci_math():
    """Wilson CI is correct at perfect/zero/degenerate n."""
    lo1, hi1 = wilson_ci(40, 40)
    assert abs(lo1 - 0.9125) < 0.01 and abs(hi1 - 1.0) < 1e-9  # p=1 → hi=1
    lo0, hi0 = wilson_ci(0, 40)
    assert lo0 == 0.0 and hi0 > 0.0 and hi0 < 0.1  # zero → (0, ~0.07)
    lo0n, hi0n = wilson_ci(0, 0)
    assert lo0n == 0.0 and hi0n == 0.0
    print(f"  ✅ Wilson: p=1 → ({lo1:.3f}, 1.0); p=0 → ({lo0:.3f}, {hi0:.3f})")


def test_ar03_good_system_measured_all_axes():
    """A known-compliant system (scorer always True) → all axes measured."""
    # Need 30+ DISTINCT probes per axis (run_arena never cycles to inflate n)
    probes = {a: [{"q": f"q-{a}-{i}", "must_inc": ["ok"]} for i in range(40)] for a in GSPC_AXES}
    profile = run_arena("good", "fake://x", scorer=_good_scorer,
                        min_n=30, per_axis_target=40,
                        probes=probes,
                        query_fn=_fake_query)
    assert len(profile.measured_axes()) == len(GSPC_AXES)
    for axis in GSPC_AXES:
        assert profile.axes[axis].pct == 1.0
        assert profile.axes[axis].n >= 30
    cand = profile.candidate_vector()
    assert len(cand) == len(GSPC_AXES)
    print(f"  ✅ known-good: {len(GSPC_AXES)}/{len(GSPC_AXES)} axes measured, pct=1.0, candidate dim {len(cand)}")


def test_ar04_bad_system_measured_all_axes():
    """A known-non-compliant system (scorer always False) → all axes measured at 0."""
    probes = {a: [{"q": f"q-{a}-{i}", "must_inc": ["ok"]} for i in range(40)] for a in GSPC_AXES}
    profile = run_arena("bad", "fake://x", scorer=_bad_scorer,
                        min_n=30, per_axis_target=40,
                        probes=probes,
                        query_fn=_fake_query)
    assert len(profile.measured_axes()) == len(GSPC_AXES)
    cand = profile.candidate_vector()
    assert all(x == 0.0 for x in cand)
    print(f"  ✅ known-bad: {len(GSPC_AXES)}/{len(GSPC_AXES)} axes measured at pct=0.0")


def test_ar05_planted_canary_separates_good_from_bad():
    """THE GATE: good and bad are separable at n≥30 with disjoint CIs.

    This is the spec §4 planted-canary test. If the instrument can't
    separate a known-good from a known-bad, it isn't ready to ship a
    verdict. Here both are measured at n=40: good pct=1.0 (CI 0.91–1.0),
    bad pct=0.0 (CI 0.0–0.07) → disjoint.
    """
    probes = {a: [{"q": f"q-{a}-{i}", "must_inc": ["ok"]} for i in range(40)] for a in GSPC_AXES}
    good = run_arena("good", "fake://x", scorer=_good_scorer, min_n=30,
                     per_axis_target=40, probes=probes, query_fn=_fake_query)
    bad = run_arena("bad", "fake://x", scorer=_bad_scorer, min_n=30,
                    per_axis_target=40, probes=probes, query_fn=_fake_query)
    g = good.axes["gov"]; b = bad.axes["gov"]
    assert g.measured and b.measured
    assert g.n >= 30 and b.n >= 30
    # Disjoint: good CI entirely above bad CI
    assert g.ci_low > b.ci_high, f"NOT separable: good CI [{g.ci_low:.3f},{g.ci_high:.3f}] vs bad [{b.ci_low:.3f},{b.ci_high:.3f}]"
    print(f"  ✅ CANARY SEPARATION: good pct=1.0 CI[{g.ci_low:.3f},{g.ci_high:.3f}] "
          f"vs bad pct=0.0 CI[{b.ci_low:.3f},{b.ci_high:.3f}] — disjoint")


def test_ar06_unmeasured_axis_excluded():
    """n < min_n → UNMEASURED, excluded from the candidate, listed in profile."""
    probes = {a: [{"q": f"q-{a}", "must_inc": ["ok"]}] for a in GSPC_AXES}
    # Force 'mcp' to have only 5 probes (min_n=30) by a bank that stops early
    small_probes = dict(probes)
    small_probes["mcp"] = [{"q": "q-mcp", "must_inc": ["ok"]}]  # only 1 probe → n=1 < 30
    profile = run_arena("small", "fake://x", scorer=_good_scorer, min_n=30,
                        per_axis_target=5, probes=small_probes, query_fn=_fake_query)
    # per_axis_target=5 < min_n=30 → EVERY axis is UNMEASURED (honest!)
    assert profile.measured_axes() == []
    assert "mcp" in profile.unmeasured_axes()
    assert profile.candidate_vector() == []
    print(f"  ✅ n<30 → UNMEASURED: measured={profile.measured_axes()}, "
          f"candidate=[] (never scores a thin sample)")


def test_ar07_contamination_gate_flags():
    """A system that echoes the answer key is flagged, not scored."""
    resp = "The answer is high-risk because Annex III applies."
    hit = contamination_check("question?", resp, answer_key=["high-risk because Annex III"])
    assert hit is not None
    print(f"  ✅ contamination gate: {hit}")


def test_ar08_measure_endpoint_summary():
    """measure_endpoint returns the summary dict with all key fields."""
    probes = {a: [{"q": f"q-{a}-{i}", "must_inc": ["ok"]} for i in range(40)] for a in GSPC_AXES}
    summary = measure_endpoint("m", "fake://x", scorer=_good_scorer, min_n=30,
                               per_axis_target=40,
                               probes=probes,
                        query_fn=_fake_query)
    assert summary["model"] == "m"
    assert summary["candidate_vector"]
    assert len(summary["measured_axes"]) == len(GSPC_AXES)
    assert "unmeasured_axes" in summary and "contamination" in summary
    assert "profile" in summary
    print(f"  ✅ measure_endpoint summary: {len(GSPC_AXES)} axes, dim={len(summary['candidate_vector'])}")


def test_ar09_self_test():
    """self_test returns a complete picture."""
    info = self_test()
    assert info["n_axes"] == len(GSPC_AXES)
    assert info["all_measured"] is True
    assert info["candidate_len"] == len(GSPC_AXES)
    assert info["all_ones"] is True
    print(f"  ✅ self_test: {len(GSPC_AXES)} axes, all measured, candidate all 1.0")


if __name__ == "__main__":
    tests = [
        test_ar01_axes_are_the_12,
        test_ar02_wilson_ci_math,
        test_ar03_good_system_measured_all_axes,
        test_ar04_bad_system_measured_all_axes,
        test_ar05_planted_canary_separates_good_from_bad,
        test_ar06_unmeasured_axis_excluded,
        test_ar07_contamination_gate_flags,
        test_ar08_measure_endpoint_summary,
        test_ar09_self_test,
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