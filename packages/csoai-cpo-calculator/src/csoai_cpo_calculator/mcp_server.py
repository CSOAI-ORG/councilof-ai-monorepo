"""MCP server for csoai-cpo-calculator.

Exposes the CPO (Co-Packaged Optics) power savings calculator as MCP tools.

This implements the MCP (Model Context Protocol) interface so the calculator
can be invoked by any MCP-compatible agent (Claude, GPT, Hermes, etc.).

The 3 tools exposed:
  - compute_cpo_savings: Compute power/cost/CO2 savings for a data center config
  - list_cpo_scenarios: List 4 pre-built scenarios (Edge, Enterprise, AI, Hyperscale)
  - render_cpo_report: Get a markdown savings report

Description quality matters. We follow the "description smell" mitigation
pattern documented in the Feb 2026 MCP study (856 tools analyzed): every
tool has PURPOSE, GUIDELINES, LIMITATIONS, PARAMETERS, EXAMPLES.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Allow running as `python -m csoai_cpo_calculator.mcp_server`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csoai_cpo_calculator import (  # noqa: E402
    DataCenterConfig,
    SavingsReport,
    SCENARIOS,
    compute_savings,
    render_all_scenarios,
)


# ===========================================================================
# MCP TOOL DESCRIPTIONS (no smell — purpose, guidelines, limitations, params)
# ===========================================================================

TOOL_DESCRIPTIONS: Dict[str, Dict[str, Any]] = {
    "compute_cpo_savings": {
        "purpose": (
            "Compute the power, cost, and CO2 savings of Co-Packaged Optics (CPO) "
            "over conventional pluggable optical transceivers for a given data "
            "center configuration. Uses published NVIDIA CPO datasheet numbers "
            "(2026): ~30W per 1.6T pluggable vs ~5W per 1.6T CPO at the package edge."
        ),
        "guidelines": [
            "Use when comparing CPO vs pluggable optics for a specific deployment.",
            "Use list_cpo_scenarios first to see pre-built configs.",
            "Results are deterministic given the inputs — no ML, no randomness.",
            "Output is a structured SavingsReport with power (W/MW), cost ($/year), "
            "and CO2 (tonnes/year) at 3 time horizons (1y, 5y, 10y).",
        ],
        "limitations": [
            "Does not model capital expenditure (capex) of CPO transceivers.",
            "Uses US/EU average electricity ($0.15/kWh). Override "
            "electricity_cost_per_kwh for your region.",
            "CO2 uses 0.4 kg CO2/kWh (global grid average).",
            "Does not model fiber reach limitations — assumes all links are within "
            "the CPO package (typically <2m).",
        ],
        "parameters": {
            "n_servers": "int — Number of servers in the data center (default 1000)",
            "links_per_server": "int — Optical links per server (default 8, typical)",
            "utilization": "float 0-1 — Link utilization factor (default 0.7)",
            "pue": "float — Power Usage Effectiveness for cooling overhead (default 1.5)",
            "bandwidth_gbps": "float — Bandwidth per link in Gbps (default 1600 = 1.6T)",
            "electricity_cost_per_kwh": "float — USD per kWh (default 0.15)",
            "description": "str — Optional label for the report",
        },
        "example": {
            "n_servers": 100000,
            "links_per_server": 8,
            "electricity_cost_per_kwh": 0.12,
        },
    },
    "list_cpo_scenarios": {
        "purpose": (
            "List the 4 pre-built CPO savings scenarios (small_edge, mid_enterprise, "
            "hyperscale, sov1_farm). Each scenario bundles realistic parameters for a "
            "typical deployment size. Use compute_cpo_savings to get the detailed numbers "
            "for any scenario."
        ),
        "guidelines": [
            "Use this first to see what configurations are pre-modeled.",
            "hyperscale is the canonical 'large cloud' scenario (100k+ servers, 16 links).",
            "sov1_farm is the canonical 'edge' scenario (1 server, koi-farm sensor hub).",
            "mid_enterprise is the canonical 'enterprise on-prem' scenario (1k servers).",
        ],
        "limitations": [
            "Pre-built scenarios are US/EU averages. Override for your region.",
            "Scenarios are static — call compute_cpo_savings for custom configs.",
        ],
        "parameters": {},
        "example": {},
    },
    "render_cpo_report": {
        "purpose": (
            "Render all 4 pre-built CPO scenarios as a single markdown report. "
            "Returns a formatted string ready to write to a file, paste into a "
            "wiki, or embed in a slide deck."
        ),
        "guidelines": [
            "Use when you need a printable summary across multiple configs.",
            "Returns a markdown string. Pipe to `tee` to save to disk.",
            "Each scenario shows power (MW), cost ($/year), CO2 (tonnes/year).",
        ],
        "limitations": [
            "Markdown only. No HTML, no PDF, no SVG.",
            "No customization per scenario — uses pre-built configs.",
        ],
        "parameters": {},
        "example": {},
    },
}


# ===========================================================================
# MCP-Style Tool Functions (callable, return JSON-serializable dicts)
# ===========================================================================

def _to_dict(obj: Any) -> Dict[str, Any]:
    """Convert dataclass to dict, recursively."""
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    return obj


def mcp_compute_cpo_savings(
    n_servers: int = 1000,
    links_per_server: int = 8,
    utilization: float = 0.7,
    pue: float = 1.5,
    bandwidth_gbps: float = 1600.0,
    electricity_cost_per_kwh: float = 0.15,
    description: str = "",
) -> Dict[str, Any]:
    """MCP tool: compute_cpo_savings (description in TOOL_DESCRIPTIONS).

    Note: pluggable and CPO watts/link are module-level constants
    (PLUGGABLE_WATTS_PER_LINK=30, CPO_WATTS_PER_LINK=9 at 1.6T) per the
    NVIDIA CPO datasheet (2026). PUE accounts for cooling overhead.
    """
    cfg = DataCenterConfig(
        n_servers=n_servers,
        links_per_server=links_per_server,
        utilization=utilization,
        pue=pue,
        bandwidth_gbps=bandwidth_gbps,
        electricity_cost_per_kwh=electricity_cost_per_kwh,
        description=description,
    )
    report = compute_savings(cfg)
    return _to_dict(report)


def mcp_list_cpo_scenarios() -> Dict[str, Any]:
    """MCP tool: list_cpo_scenarios (description in TOOL_DESCRIPTIONS)."""
    return {
        "scenarios": [
            {
                "name": name,
                "description": cfg.description,
                "n_servers": cfg.n_servers,
                "links_per_server": cfg.links_per_server,
            }
            for name, cfg in SCENARIOS.items()
        ],
    }


def mcp_render_cpo_report() -> Dict[str, Any]:
    """MCP tool: render_cpo_report (description in TOOL_DESCRIPTIONS)."""
    return {"markdown": render_all_scenarios()}


# ===========================================================================
# Tool Registry (for MCP servers to introspect)
# ===========================================================================

MCP_TOOLS = {
    "compute_cpo_savings": {
        "function": mcp_compute_cpo_savings,
        "description": TOOL_DESCRIPTIONS["compute_cpo_savings"],
    },
    "list_cpo_scenarios": {
        "function": mcp_list_cpo_scenarios,
        "description": TOOL_DESCRIPTIONS["list_cpo_scenarios"],
    },
    "render_cpo_report": {
        "function": mcp_render_cpo_report,
        "description": TOOL_DESCRIPTIONS["render_cpo_report"],
    },
}


def list_tools() -> Dict[str, Any]:
    """Return all MCP tools with descriptions (introspectable by agents)."""
    return {
        name: {
            "name": name,
            "purpose": meta["description"]["purpose"],
            "guidelines": meta["description"]["guidelines"],
            "limitations": meta["description"]["limitations"],
            "parameters": meta["description"]["parameters"],
        }
        for name, meta in MCP_TOOLS.items()
    }


if __name__ == "__main__":
    # Smoke test: list all tools + their descriptions
    import json
    print(json.dumps(list_tools(), indent=2)[:2000])
