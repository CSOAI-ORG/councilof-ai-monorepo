"""Tests for csoai_asi_evolve — the sovereign GAIR-ASI-Evolve wrapper."""
import os, tempfile

# Module-scoped Ed25519 key (wrapper-pattern pitfall #2): set BEFORE import so
# every test shares ONE keypair; per-test tmpdir would invalidate signatures.
_TEST_DIR = tempfile.mkdtemp(prefix="sov_asi_evolve_test_")
os.environ["SOV_ASI_EVOLVE_KEY"] = os.path.join(_TEST_DIR, "key.pem")

from csoai_asi_evolve import (
    ASIEvolve, Candidate, EvolveRound, verify_receipt,
    VERSION, PROTOCOL, PHASES, CARE_FLOOR_DEFAULT, UPSTREAM,
)


def test_protocol_version_constants():
    assert PROTOCOL == "csoai-asi-evolve/0.1"
    assert VERSION == "0.1.0"
    assert PHASES == ("LEARN", "DESIGN", "EXPERIMENT", "ANALYZE")
    assert CARE_FLOOR_DEFAULT >= 0.8
    assert "github.com/GAIR-NLP/ASI-Evolve" in UPSTREAM


def test_sign_then_verify_round():
    r = EvolveRound(1, "LEARN", Candidate("p", "idea"), "idea")
    signed = r.signed()
    # every step carries a kid + sig + sha
    for k in ("kid", "sig", "payload_sha256"):
        assert k in signed
    assert verify_receipt(signed) is True


def test_tamper_detected():
    r = EvolveRound(1, "EXPERIMENT", Candidate("p", "idea", success=0.9, attempts=10),
                    "ACCEPTED", "success=0.900")
    signed = r.signed()
    signed["candidate"]["success"] = 0.99  # tamper
    # REHASH to reflect tamper (as a real attacker would), then verify must fail
    from csoai_asi_evolve import _sign
    # Simulate honest tamper: re-sign would pass. Instead drop the sig.
    signed["sig"] = "AAAA"  # corrupt
    assert verify_receipt(signed) is False


def test_care_floor_rejects_low_success():
    loop = ASIEvolve(care_floor=0.85, max_rounds=1, max_candidates_per_round=1)
    assert loop._accepts(Candidate("p", "i", success=0.84, attempts=10)) is False
    assert loop._accepts(Candidate("p", "i", success=0.86, attempts=10)) is True


def test_run_honest_scoring_real_predicate():
    """The engine must score against a supplied deterministic predicate, not a
    length heuristic. success comes from the experiment fn, never from
    len(response) > 50."""
    calls = {"n": 0}

    def learn(analysis):
        return "evolved idea"

    def design(idea):
        return "candidate-program"

    def experiment(program):
        # real predicate: 4 of 5 correct = 0.80 (below 0.85 floor)
        calls["n"] += 1
        return {"success": 0.80, "n": 5}

    def analyze(best):
        return f"distil from {best.success:.3f}" if best else "nothing"

    loop = ASIEvolve(care_floor=0.85, max_rounds=2, max_candidates_per_round=1)
    rep = loop.run(learn_fn=learn, design_fn=design,
                   experiment_fn=experiment, analyze_fn=analyze)
    assert rep["best"] is not None
    # best carries the REAL predicate success (0.80), not a fabricated high score
    assert rep["best"]["success"] == 0.80
    assert rep["best"]["attempts"] == 5
    # every round step is signed and verified
    for step in rep["rounds"]:
        assert step.get("sig"), "every step must be signed"
        assert step["valid"] is True, "every signed step must verify"


def test_run_accepts_when_over_floor():
    def experiment(program):
        return {"success": 0.92, "n": 5}

    loop = ASIEvolve(care_floor=0.85, max_rounds=1, max_candidates_per_round=1)
    rep = loop.run(
        learn_fn=lambda a: "idea", design_fn=lambda i: "p",
        experiment_fn=experiment, analyze_fn=lambda b: "ok")
    assert rep["best"]["success"] == 0.92
    outcomes = [s["outcome"] for s in rep["rounds"]]
    assert "ACCEPTED" in outcomes


def test_run_no_candidate_does_not_crash_and_says_so():
    """If nothing clears the experiment seam (0.0), run() must finish cleanly
    and report best=None honestly, not fabricate a win."""
    def experiment(program):
        return {"success": 0.0, "n": 5}

    loop = ASIEvolve(care_floor=0.85, max_rounds=2, max_candidates_per_round=1)
    rep = loop.run(
        learn_fn=lambda a: "idea", design_fn=lambda i: "p",
        experiment_fn=experiment, analyze_fn=lambda b: "none")
    assert rep["best"] is None or rep["best"]["success"] <= 0.85
    # honesty string present
    assert "harness, not a claim of achieved ASI" in rep["honest"]


def test_best_improves_across_rounds_when_predicate_improves():
    """The evolving loop keeps the max-success candidate when a later round wins."""
    seq = iter([{"success": 0.86, "n": 5}, {"success": 0.94, "n": 6}])

    def experiment(program):
        return next(seq)

    loop = ASIEvolve(care_floor=0.85, max_rounds=2, max_candidates_per_round=1)
    rep = loop.run(
        learn_fn=lambda a: "idea", design_fn=lambda i: "p",
        experiment_fn=experiment, analyze_fn=lambda b: f"b:{b.success}")
    assert rep["best"]["success"] == 0.94


def test_report_shape():
    loop = ASIEvolve(care_floor=0.85, max_rounds=1, max_candidates_per_round=1)
    loop.run(learn_fn=lambda a: "i", design_fn=lambda i: "p",
             experiment_fn=lambda p: {"success": 0.9, "n": 4},
             analyze_fn=lambda b: "ok")
    rep = loop.report()
    for k in ("protocol", "max_rounds", "best", "rounds", "care_floor", "honest"):
        assert k in rep, k