"""Tests for csoai-dream — humanoid dream-loop harness."""
from __future__ import annotations

import pytest
from csoai_dream import (
    CARE_FLOOR,
    DreamPolicy,
    DreamState,
    DreamTrajectory,
    article0_dream_guard,
    dream_trajectory,
    sample_grasp_policy,
    sample_walk_policy,
)


def test_01_care_floor_constant():
    assert CARE_FLOOR == 0.95


def test_02_dream_state_constructs():
    s = DreamState(
        t=0.0,
        jspace_position={"x": 0.1, "y": 0.2, "z": 0.3},
        action="walk-forward",
        sigma=0.01,
    )
    assert s.t == 0.0
    assert s.action == "walk-forward"
    assert s.sigma == 0.01


def test_03_dream_trajectory_fingerprint_stable():
    traj = DreamTrajectory(
        trajectory_id="x",
        states=[
            DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.01),
            DreamState(t=1, jspace_position={"x":0.2}, action="b", sigma=0.02),
        ],
        initial_state="s",
        policy_id="p",
    )
    assert traj.fingerprint() == traj.fingerprint()
    assert len(traj.fingerprint()) == 32


def test_04_dream_trajectory_length():
    traj = DreamTrajectory(
        trajectory_id="x",
        states=[
            DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.01),
            DreamState(t=1, jspace_position={"x":0.2}, action="b", sigma=0.02),
        ],
    )
    assert traj.length() == 2


def test_05_dream_trajectory_mean_sigma():
    traj = DreamTrajectory(
        trajectory_id="x",
        states=[
            DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.02),
            DreamState(t=1, jspace_position={"x":0.2}, action="b", sigma=0.04),
        ],
    )
    assert abs(traj.mean_sigma() - 0.03) < 1e-9


def test_06_dream_trajectory_max_sigma():
    traj = DreamTrajectory(
        trajectory_id="x",
        states=[
            DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.02),
            DreamState(t=1, jspace_position={"x":0.2}, action="b", sigma=0.10),
        ],
    )
    assert traj.max_sigma() == 0.10


def test_07_dream_trajectory_within_calibration():
    """Within calibration = max σ ≤ 0.05 (per sovos-sigma-calibration)."""
    traj = DreamTrajectory(
        trajectory_id="x",
        states=[DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.03)],
    )
    assert traj.is_within_calibration(ceiling=0.05)
    traj2 = DreamTrajectory(
        trajectory_id="x",
        states=[DreamState(t=0, jspace_position={"x":0.1}, action="a", sigma=0.10)],
    )
    assert not traj2.is_within_calibration(ceiling=0.05)


def test_08_dream_policy_constructs():
    p = DreamPolicy(
        policy_id="walk",
        description="walk forward",
        max_length=16,
        sigma_ceiling=0.05,
        banned_actions=["deploy-drone"],
    )
    assert p.policy_id == "walk"
    assert p.max_length == 16


def test_09_dream_trajectory_respects_max_length():
    p = DreamPolicy(policy_id="x", description="x", max_length=4, sigma_ceiling=0.05)
    traj = dream_trajectory(p, initial_state="start", n_steps=20)
    assert traj.length() == 4  # capped at max_length


def test_10_dream_trajectory_default_length():
    p = DreamPolicy(policy_id="x", description="x", max_length=100, sigma_ceiling=0.05)
    traj = dream_trajectory(p, initial_state="start", n_steps=8)
    assert traj.length() == 8


def test_11_dream_trajectory_sigma_grows():
    """σ grows with horizon (deeper dream = less certain)."""
    p = DreamPolicy(policy_id="x", description="x", max_length=100, sigma_ceiling=0.05)
    traj = dream_trajectory(p, initial_state="start", n_steps=5)
    sigmas = [s.sigma for s in traj.states]
    for i in range(1, len(sigmas)):
        assert sigmas[i] > sigmas[i - 1]


def test_12_article0_guard_banned_action_detected():
    p = DreamPolicy(
        policy_id="x", description="x", max_length=8, sigma_ceiling=1.0,
        banned_actions=["deploy-an-autonomous-drone"],
    )
    states = [
        DreamState(t=0, jspace_position={"x":0.1}, action="walk", sigma=0.01),
        DreamState(t=1, jspace_position={"x":0.2}, action="deploy-an-autonomous-drone", sigma=0.02),
    ]
    traj = DreamTrajectory(trajectory_id="x", states=states, policy_id="x")
    report = article0_dream_guard(p, traj)
    assert not report["passed"]
    assert 1 in report["banned_action_states"]


def test_13_article0_guard_oversigma_detected():
    p = DreamPolicy(
        policy_id="x", description="x", max_length=8, sigma_ceiling=0.05,
        banned_actions=[],
    )
    states = [
        DreamState(t=0, jspace_position={"x":0.1}, action="walk", sigma=0.01),
        DreamState(t=1, jspace_position={"x":0.2}, action="run", sigma=0.20),
    ]
    traj = DreamTrajectory(trajectory_id="x", states=states, policy_id="x")
    report = article0_dream_guard(p, traj)
    assert not report["passed"]
    assert 1 in report["oversigma_states"]


def test_14_article0_guard_passes_clean_trajectory():
    p = DreamPolicy(
        policy_id="x", description="x", max_length=8, sigma_ceiling=0.05,
        banned_actions=["deploy-drone"],
    )
    traj = dream_trajectory(p, initial_state="start", n_steps=5)
    report = article0_dream_guard(p, traj)
    assert report["passed"]
    assert report["banned_action_states"] == []
    assert report["oversigma_states"] == []


def test_15_sample_walk_policy_default():
    p = sample_walk_policy()
    assert "banned" in p.description.lower() or "deploy" in str(p.banned_actions).lower()
    # walk-policy bans deploy-an-autonomous-drone and mass surveillance
    assert "deploy-an-autonomous-drone" in p.banned_actions


def test_16_sample_grasp_policy_no_bans():
    p = sample_grasp_policy()
    assert p.banned_actions == []


def test_17_no_kinetic_in_default_policies():
    """No default policy contains kinetic patterns in its banned list."""
    for p in [sample_walk_policy(), sample_grasp_policy()]:
        for b in p.banned_actions:
            assert "kinetic" not in b.lower()
            assert "weapon" not in b.lower()
            assert "kill chain" not in b.lower()


def test_18_dream_trajectory_initial_state_propagates():
    p = DreamPolicy(policy_id="x", description="x", max_length=4, sigma_ceiling=0.05)
    traj = dream_trajectory(p, initial_state="robot-at-table-with-cup", n_steps=3)
    assert traj.initial_state == "robot-at-table-with-cup"


def test_19_dream_trajectory_deterministic_seed():
    p = DreamPolicy(policy_id="x", description="x", max_length=4, sigma_ceiling=0.05)
    t1 = dream_trajectory(p, initial_state="s", n_steps=3, seed=42)
    t2 = dream_trajectory(p, initial_state="s", n_steps=3, seed=42)
    assert t1.fingerprint() == t2.fingerprint()


def test_20_article0_guard_within_calibration_default():
    """Default walk-policy trajectory passes the guard (stub σ grows but capped)."""
    p = sample_walk_policy()
    traj = dream_trajectory(p, initial_state="start", n_steps=4)
    # σ at step 4 = 0.04, ceiling = 0.05 → within calibration
    report = article0_dream_guard(p, traj)
    # if no banned actions appear in stub action names, it should pass
    assert report["passed"]