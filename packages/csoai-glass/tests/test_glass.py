"""Tests for csoai-glass — Tier-0 Glass OS."""
from __future__ import annotations

from csoai_glass import (
    HaloPoint,
    GlassConfig,
    GlassFrame,
    halos_from_signal_axis,
    render_glass_html,
)


def test_01_halo_point_default_sigma_is_correct():
    """sigma = 1 - confidence."""
    h = HaloPoint(x=0, y=0, z=0.5, confidence=0.7, label="test")
    assert abs(h.sigma - 0.3) < 1e-9


def test_02_halo_point_sigma_clamped():
    h = HaloPoint(x=0, y=0, z=0.0, confidence=1.5)  # > 1 confidence
    assert h.sigma == 0.0


def test_03_glass_config_default_legal():
    """Default ECE ceiling of 0.05 passes the calibration gate."""
    cfg = GlassConfig()
    assert cfg.is_legal_to_ship()


def test_04_glass_config_too_loose_illegal():
    cfg = GlassConfig(uncertainty_calibration_required=0.10)
    assert not cfg.is_legal_to_ship()


def test_05_halos_from_signal_axis_creates_12_halos():
    """12 axes (canonical GSPC count)."""
    axes = ["gov", "agi", "prv", "asi", "mcp", "oss", "mach", "care", "xr", "det", "art5", "swarm"]
    vec = [0.1] * 12
    halos = halos_from_signal_axis(vec, axes)
    assert len(halos) == 12


def test_05b_halos_can_repeat_axis_names_for_longer_vectors():
    """If vector > axis_names, names repeat (canonical use: 12 axes vs 12 names)."""
    halos = halos_from_signal_axis([0.5] * 12, ["governance", "agency", "privacy"])
    assert len(halos) == 12
    # First three halos take from the 3 names cycled
    assert halos[0].label == "governance"
    assert halos[1].label == "agency"
    assert halos[2].label == "privacy"
    assert halos[3].label == "governance"  # cycle


def test_06_halos_labels_match_axes():
    axes = ["gov", "agi", "prv", "asi", "mcp", "oss", "mach", "care", "xr", "det", "art5", "swarm"]
    halos = halos_from_signal_axis([0.1] * 12, axes)
    for halo, name in zip(halos, axes):
        assert halo.label == name


def test_07_halos_confidence_is_complement_of_axis():
    """axis 0.3 → confidence 0.7 → sigma 0.3."""
    halos = halos_from_signal_axis([0.3] * 12, ["x"] * 12)
    for h in halos:
        assert abs(h.confidence - 0.7) < 1e-9
        assert abs(h.sigma - 0.3) < 1e-9


def test_08_halos_grid_4x3():
    """12 halos laid out on a 4-column grid (col 0..3, row 0..2)."""
    halos = halos_from_signal_axis([0.5] * 12, [f"a{i}" for i in range(12)])
    xs = sorted(set(round(h.x, 4) for h in halos))
    ys = sorted(set(round(h.y, 4) for h in halos))
    # 4 distinct x positions (cols), 3 distinct y positions (rows)
    assert len(xs) == 4
    assert len(ys) == 3


def test_09_halos_provenance_format():
    halos = halos_from_signal_axis([0.5] * 12, ["governance", "agency", "privacy"])
    # provenance = "sigil:" + first 3 chars of axis (lowercased)
    assert halos[0].provenance == "sigil:gov"
    assert halos[1].provenance == "sigil:age"
    assert halos[2].provenance == "sigil:pri"


def test_10_halos_vector_mismatch_raises():
    import pytest
    with pytest.raises(ValueError):
        halos_from_signal_axis([0.1] * 5, ["x"] * 12)


def test_11_glass_frame_to_dict():
    halos = halos_from_signal_axis([0.2] * 12, [f"a{i}" for i in range(12)])
    frame = GlassFrame(halos=halos, ece=0.04, timestamp=1234.5)
    d = frame.to_dict()
    assert "halos" in d
    assert len(d["halos"]) == 12
    assert d["ece"] == 0.04


def test_12_render_glass_html_basic():
    html = render_glass_html()
    assert "<canvas" in html
    assert "SOVOS Glass" in html
    assert "three@0.160.0" in html  # three.js import
    assert "getUserMedia" in html
    assert "12" in html  # axis grid


def test_13_render_glass_html_respects_config():
    cfg = GlassConfig(parallax_strength=0.10, sigma_halo_max_radius=120.0)
    html = render_glass_html(cfg)
    assert "0.10" in html
    assert "120" in html


def test_14_no_kinetic_in_html():
    """Glass must not contain kinetic-targeting patterns anywhere."""
    html = render_glass_html()
    assert "kinetic" not in html.lower()
    assert "kill chain" not in html.lower()
    assert "weapon" not in html.lower()


def test_15_sigma_calibration_gate_is_honest():
    """ECE ≤ 0.05 → ship; > 0.05 → don't ship. The dead-grey rendering
    is the fallback. Mirrors sovos-sigma-calibration's CalibrationGate.
    """
    # ship-able at exactly 0.05
    assert GlassConfig(uncertainty_calibration_required=0.05).is_legal_to_ship()
    # not ship-able at 0.06
    assert not GlassConfig(uncertainty_calibration_required=0.06).is_legal_to_ship()


def test_16_halos_z_uses_raw_axis_value():
    """Depth z = raw axis value (0 = front, 1 = back)."""
    halos = halos_from_signal_axis([0.0, 0.5, 1.0] + [0.5] * 9, ["a"] * 12)
    assert halos[0].z == 0.0
    assert halos[1].z == 0.5
    assert halos[2].z == 1.0