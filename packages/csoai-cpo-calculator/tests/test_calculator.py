"""Tests for the SOVOS CPO Power Savings Calculator.

10 tests covering:
- Constants (NVIDIA CPO numbers)
- Basic single-server calculation
- Hyperscale data center
- Edge deployment
- Energy / cost / CO2 conversions
- Latency savings
- Cross-validation: small + large give same per-link savings
- All 4 pre-built scenarios
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_cpo_calculator import (
    DataCenterConfig,
    SavingsReport,
    PLUGGABLE_WATTS_PER_LINK,
    CPO_WATTS_PER_LINK,
    PLUGGABLE_LATENCY_NS,
    CPO_LATENCY_NS,
    compute_savings,
    SCENARIOS,
    render_all_scenarios,
)


def test_01_constants_match_nvidia_datasheet():
    """The published NVIDIA CPO numbers must be exact."""
    assert PLUGGABLE_WATTS_PER_LINK == 30.0
    assert CPO_WATTS_PER_LINK == 9.0
    assert PLUGGABLE_LATENCY_NS == 500.0
    assert CPO_LATENCY_NS == 50.0
    # 70% power reduction: (30-9)/30 = 0.7
    assert (PLUGGABLE_WATTS_PER_LINK - CPO_WATTS_PER_LINK) / PLUGGABLE_WATTS_PER_LINK == 0.7
    print("  ✅ constants: 30W → 9W, 500ns → 50ns (NVIDIA CPO datasheet)")


def test_02_single_server_savings():
    """1 server, 8 links, 70% util, 1.5 PUE, $0.15/kWh."""
    cfg = DataCenterConfig(n_servers=1, links_per_server=8)
    r = compute_savings(cfg)
    # 8 links × 30W × 0.7 = 168W pluggable; 8×9×0.7 = 50.4W CPO
    # Saved = 117.6 W
    assert abs(r.power_saved_w - 117.6) < 0.01
    assert abs(r.power_reduction_pct - 70.0) < 0.01
    # Annual kWh = 117.6 × 8760 × 1.5 / 1000 = 1545.264 kWh
    assert abs(r.annual_kwh_saved - 1545.264) < 0.01
    # $ saved = 1545.264 × 0.15 = $231.79
    assert abs(r.annual_dollars_saved - 231.79) < 0.01
    print(f"  ✅ single server: {r.power_saved_w:.1f}W saved, "
          f"{r.annual_kwh_saved:.0f} kWh/yr, ${r.annual_dollars_saved:.2f}/yr")


def test_03_hyperscale_savings():
    """100k servers × 16 links = 1.6M links."""
    r = compute_savings(SCENARIOS["hyperscale"])
    expected_links = 100000 * 16
    assert r.n_links == expected_links
    # Power saved = 1.6M × 21 × 0.85 = 28.56 MW
    assert abs(r.power_saved_w - 28_560_000) < 100
    # Annual kWh = 28.56MW × 8760h × 1.4 = 350,196,480 kWh
    assert r.annual_kwh_saved > 350_000_000
    # $ saved at $0.08/kWh = ~$28M/year
    assert r.annual_dollars_saved > 28_000_000
    print(f"  ✅ hyperscale: {r.power_saved_w/1e6:.1f} MW saved, "
          f"${r.annual_dollars_saved/1e6:.1f}M/yr, "
          f"{r.annual_co2_avoided_kg/1e6:.0f}k tonnes CO₂/yr")


def test_04_edge_deployment():
    """sov1_farm: 1 server, 2 links — small but proportional."""
    r = compute_savings(SCENARIOS["sov1_farm"])
    assert r.n_links == 2
    # 2 × 21 × 0.3 = 12.6 W saved
    assert abs(r.power_saved_w - 12.6) < 0.01
    # At $0.25/kWh, slightly more per kWh savings
    assert r.annual_dollars_saved > 30
    print(f"  ✅ sov1_farm edge: {r.power_saved_w:.1f}W saved, "
          f"${r.annual_dollars_saved:.2f}/yr")


def test_05_latency_savings():
    """Latency savings: 450ns per hop, 90% reduction."""
    cfg = DataCenterConfig(n_servers=10)
    r = compute_savings(cfg)
    assert r.latency_saved_per_hop_ns == 450.0
    assert r.latency_reduction_pct == 90.0
    print(f"  ✅ latency: {r.latency_saved_per_hop_ns:.0f}ns saved per hop "
          f"({r.latency_reduction_pct:.0f}% reduction)")


def test_06_co2_avoided_uses_iea_factor():
    """CO2 uses 0.4 kg/kWh global average (IEA)."""
    cfg = DataCenterConfig(n_servers=1000, links_per_server=8,
                            electricity_cost_per_kwh=0.10)
    r = compute_savings(cfg)
    # power_saved = 8000 × 21 × 0.7 = 117,600 W
    # annual_kwh = 117600 × 8760 × 1.5 / 1000 = 1,545,264 kWh
    # co2 = 1,545,264 × 0.4 = 618,105.6 kg
    assert abs(r.annual_co2_avoided_kg - 618_105.6) < 1
    print(f"  ✅ CO₂ avoided: {r.annual_co2_avoided_kg:.0f} kg/yr "
          f"({r.annual_co2_avoided_kg / 1000:.1f} tonnes) — "
          f"equivalent to {r.trees_equivalent:.0f} trees")


def test_07_trees_equivalent_uses_usfs_factor():
    """21 kg CO2/tree/year — US Forest Service."""
    cfg = DataCenterConfig(n_servers=100, links_per_server=4)
    r = compute_savings(cfg)
    # 400 × 21 × 0.7 = 5,880 W saved
    # annual_kwh = 5880 × 8760 × 1.5 / 1000 = 77,263.2 kWh
    # co2 = 77,263.2 × 0.4 = 30,905.28 kg
    # trees = 30,905.28 / 21 = 1,471.68
    assert abs(r.trees_equivalent - 1471.68) < 1
    print(f"  ✅ trees equivalent: {r.trees_equivalent:.0f} (USFS 21 kg/tree/year)")


def test_08_per_link_savings_invariant_to_scale():
    """A 100-server and 1000-server config should have the same per-link savings."""
    cfg_small = DataCenterConfig(n_servers=100, links_per_server=8, utilization=0.7, pue=1.0)
    cfg_large = DataCenterConfig(n_servers=1000, links_per_server=8, utilization=0.7, pue=1.0)
    r_small = compute_savings(cfg_small)
    r_large = compute_savings(cfg_large)
    # Both should have 70% reduction
    assert r_small.power_reduction_pct == 70.0
    assert r_large.power_reduction_pct == 70.0
    # Per-link yearly savings should be the same
    # small: 800 × 21 × 0.7 = 11,760 W; 11,760 × 8760 × 1 / 1000 = 103,017.6 kWh
    # large: 8000 × 21 × 0.7 = 117,600 W; 117,600 × 8760 × 1 / 1000 = 1,030,176 kWh
    # kWh per link should be invariant
    kwh_per_link_small = r_small.annual_kwh_saved / r_small.n_links
    kwh_per_link_large = r_large.annual_kwh_saved / r_large.n_links
    assert abs(kwh_per_link_small - kwh_per_link_large) < 0.01
    print(f"  ✅ per-link savings invariant: {kwh_per_link_small:.1f} kWh/yr/link "
          f"(same for {r_small.n_links} and {r_large.n_links}-link configs)")


def test_09_all_scenarios_render():
    """All 4 pre-built scenarios render to markdown without errors."""
    md = render_all_scenarios()
    assert "CPO Power Savings Report" in md
    assert "small_edge" in md
    assert "mid_enterprise" in md
    assert "hyperscale" in md
    assert "sov1_farm" in md
    # The hyperscale scenario should have $M-scale savings
    assert "$" in md
    print(f"  ✅ all 4 scenarios render: {len(md)} chars of markdown")


def test_10_savings_report_to_markdown_includes_numbers():
    """The markdown report must include actual computed numbers, not placeholders."""
    cfg = DataCenterConfig(n_servers=500, links_per_server=8,
                            description="Test DC", electricity_cost_per_kwh=0.12)
    r = compute_savings(cfg)
    md = r.to_markdown()
    assert "Test DC" in md
    assert f"{r.n_links:,}" in md
    # Power saved in W (with comma)
    assert f"{r.power_saved_w:,.0f}" in md
    # Annual kWh saved
    assert f"{r.annual_kwh_saved:,.0f}" in md
    # Source attribution
    assert "NVIDIA" in md
    print(f"  ✅ markdown report includes: DC name, link count, power saved, "
          f"kWh saved, NVIDIA attribution")


def main():
    tests = [
        test_01_constants_match_nvidia_datasheet,
        test_02_single_server_savings,
        test_03_hyperscale_savings,
        test_04_edge_deployment,
        test_05_latency_savings,
        test_06_co2_avoided_uses_iea_factor,
        test_07_trees_equivalent_uses_usfs_factor,
        test_08_per_link_savings_invariant_to_scale,
        test_09_all_scenarios_render,
        test_10_savings_report_to_markdown_includes_numbers,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
