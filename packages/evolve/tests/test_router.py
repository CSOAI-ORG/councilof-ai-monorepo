"""Tests for the frozen split-conformal router predicate."""

from __future__ import annotations

import math

import numpy as np

from evolve import Router, calibrate, coverage_bounds, route


def test_route_pure_comparison():
    assert route(0.5, 1.0) == "auto"
    assert route(1.0, 1.0) == "auto"      # boundary is inclusive (score <= q_hat)
    assert route(1.0001, 1.0) == "escalate"


def test_route_infinite_thresholds():
    assert route(1e9, math.inf) == "auto"       # +inf accepts everything
    assert route(-1e9, -math.inf) == "escalate"  # -inf escalates everything


def test_router_is_frozen_and_deterministic():
    r = Router(0.7, alpha=0.1, n_calib=100)
    scores = [0.1, 0.7, 0.700001, 0.9]
    first = [r(s) for s in scores]
    second = [r.decide(s) for s in scores]
    assert first == second == ["auto", "auto", "escalate", "escalate"]
    assert r.q_hat == 0.7  # unchanged


def test_router_realizes_the_90_10_split():
    """Calibrate at alpha=0.1 and confirm ~90% of fresh items route to auto."""
    rng = np.random.default_rng(3)
    calib = rng.standard_normal(500)
    q = calibrate(calib.tolist(), 0.10)
    r = Router(q, alpha=0.10, n_calib=500)

    test = rng.standard_normal(20000)
    auto = sum(1 for s in test if r(s) == "auto")
    frac_auto = auto / test.size

    lo, hi = coverage_bounds(500, 0.10)
    # auto-rate == coverage; must sit in the finite-sample sandwich (+ MC slack).
    assert lo - 0.01 <= frac_auto <= hi + 0.01
    # sanity: it really is ~90/10, not 50/50 or 99/1
    assert 0.87 <= frac_auto <= 0.93
