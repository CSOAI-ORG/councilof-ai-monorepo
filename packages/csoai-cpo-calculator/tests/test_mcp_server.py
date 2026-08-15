"""Tests for the csoai-cpo-calculator MCP server interface."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_cpo_calculator.mcp_server import (
    MCP_TOOLS,
    TOOL_DESCRIPTIONS,
    list_tools,
    mcp_compute_cpo_savings,
    mcp_list_cpo_scenarios,
    mcp_render_cpo_report,
)


def test_m01_three_tools_registered():
    """Exactly 3 MCP tools should be registered."""
    assert len(MCP_TOOLS) == 3
    assert set(MCP_TOOLS.keys()) == {
        "compute_cpo_savings",
        "list_cpo_scenarios",
        "render_cpo_report",
    }
    print(f"  ✅ 3 MCP tools registered: {list(MCP_TOOLS.keys())}")


def test_m02_descriptions_have_no_smells():
    """Per Feb 2026 MCP study: descriptions must have purpose/guidelines/limitations/params.

    A description "smell" is when a tool is missing any of these 4 fields.
    """
    for name, desc in TOOL_DESCRIPTIONS.items():
        assert "purpose" in desc, f"{name}: missing purpose"
        assert "guidelines" in desc and len(desc["guidelines"]) >= 1, f"{name}: missing guidelines"
        assert "limitations" in desc and len(desc["limitations"]) >= 1, f"{name}: missing limitations"
        assert "parameters" in desc, f"{name}: missing parameters"
        # purpose must be substantial (>=100 chars)
        assert len(desc["purpose"]) >= 100, f"{name}: purpose too short ({len(desc['purpose'])} chars)"
        print(f"  ✅ {name}: purpose={len(desc['purpose'])}c, "
              f"guidelines={len(desc['guidelines'])}, limitations={len(desc['limitations'])}")


def test_m03_compute_cpo_savings_basic():
    """Hyperscale config: 100k servers, 8 links, 0.7 utilization, PUE 1.5."""
    r = mcp_compute_cpo_savings(
        n_servers=100_000,
        links_per_server=8,
        utilization=0.7,
        pue=1.5,
        electricity_cost_per_kwh=0.15,
    )
    # Power saved should be substantial (millions of watts)
    assert r["power_saved_w"] > 1e7, f"expected > 10 MW saved, got {r['power_saved_w']:.0f} W"
    # Annual savings should be millions of dollars
    assert r["annual_dollars_saved"] > 1e6, f"expected > $1M/yr, got ${r['annual_dollars_saved']:.0f}"
    # CO2 should be tens of thousands of tonnes
    assert r["annual_co2_avoided_kg"] > 1e7, f"expected > 10M kg CO2/yr, got {r['annual_co2_avoided_kg']:.0f}"
    print(f"  ✅ hyperscale: {r['power_saved_w']/1e6:.1f} MW saved, "
          f"${r['annual_dollars_saved']/1e6:.1f}M/yr, "
          f"{r['annual_co2_avoided_kg']/1e6:.1f}M kg CO2/yr")


def test_m04_compute_cpo_savings_edge():
    """Edge config: 10 servers, 4 links, low utilization."""
    r = mcp_compute_cpo_savings(n_servers=10, links_per_server=4, utilization=0.3)
    # Power saved should be small (hundreds of watts)
    assert r["power_saved_w"] > 100, f"edge should save at least 100W, got {r['power_saved_w']:.0f}"
    assert r["power_saved_w"] < 1e5, f"edge should save < 100kW, got {r['power_saved_w']:.0f}"
    print(f"  ✅ edge: {r['power_saved_w']:.0f} W saved (small but real)")


def test_m05_list_cpo_scenarios_has_four():
    """Should expose the 4 pre-built scenarios: small_edge, mid_enterprise, hyperscale, sov1_farm."""
    r = mcp_list_cpo_scenarios()
    names = [s["name"] for s in r["scenarios"]]
    assert len(names) == 4, f"expected 4 scenarios, got {len(names)}: {names}"
    expected = {"small_edge", "mid_enterprise", "hyperscale", "sov1_farm"}
    assert set(names) == expected, f"missing scenarios: {expected - set(names)}"
    print(f"  ✅ 4 scenarios: {names}")


def test_m06_render_cpo_report_is_markdown():
    """render_cpo_report should return a markdown string with section headers."""
    r = mcp_render_cpo_report()
    md = r["markdown"]
    assert "# " in md, "report must have markdown headers"
    assert "MW" in md or "W" in md, "report must mention power units"
    assert "$" in md or "USD" in md or "dollars" in md.lower(), "report must mention currency"
    print(f"  ✅ report: {len(md)} chars, contains headers + units + currency")


def test_m07_list_tools_introspectable():
    """list_tools should expose name, purpose, guidelines, limitations, parameters."""
    tools = list_tools()
    for name, t in tools.items():
        assert "name" in t
        assert "purpose" in t
        assert "guidelines" in t
        assert "limitations" in t
        assert "parameters" in t
    print(f"  ✅ list_tools: introspectable shape (5 fields per tool)")


if __name__ == "__main__":
    tests = [
        test_m01_three_tools_registered,
        test_m02_descriptions_have_no_smells,
        test_m03_compute_cpo_savings_basic,
        test_m04_compute_cpo_savings_edge,
        test_m05_list_cpo_scenarios_has_four,
        test_m06_render_cpo_report_is_markdown,
        test_m07_list_tools_introspectable,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
