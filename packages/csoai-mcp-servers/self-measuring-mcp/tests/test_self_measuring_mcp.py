"""test_self_measuring_mcp — the self-measuring MCP server (Layer-1 surface)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from self_measuring_mcp import (SELF_METRICS, TOOL_SCHEMA, list_tools,
                                 self_measure)

COMPLIANT = {"license_declared": 1.0, "model_card_present": 1.0,
             "provenance_declared": 0.8, "logs_retained": 1.0,
             "oversight_enabled": 1.0, "eval_open": 0.9}
NONCOMPLIANT = {"license_declared": 0.1, "model_card_present": 0.0,
                "provenance_declared": 0.0, "logs_retained": 0.2,
                "oversight_enabled": 0.0, "eval_open": 0.0}


def test_tool_schema_present():
    assert TOOL_SCHEMA["name"] == "self_measure"
    assert "entity" in TOOL_SCHEMA["inputSchema"]["properties"]
    tools = list_tools()
    assert tools[0]["name"] == "self_measure"


def test_all_metrics_covered_by_schema():
    props = TOOL_SCHEMA["inputSchema"]["properties"]["metrics"]
    assert props  # metrics dict accepted


def test_self_measure_produces_card():
    result = self_measure("demo-agent", COMPLIANT)
    # both signed (with sovos-city) and standalone fallback yield facts
    assert result["entity"] == "demo-agent"
    assert isinstance(result["facts"], list)
    assert len(result["facts"]) == len(SELF_METRICS)
    # verdicts are deterministic PASS/WATCH/FAIL
    assert set(f["verdict"] for f in result["facts"]) <= {"PASS", "WATCH", "FAIL"}


def test_compliant_vs_noncompliant_differ():
    good = self_measure("good", COMPLIANT)
    bad = self_measure("bad", NONCOMPLIANT)
    good_pass = sum(1 for f in good["facts"] if f["verdict"] == "PASS")
    bad_pass = sum(1 for f in bad["facts"] if f["verdict"] == "PASS")
    assert good_pass > bad_pass


def test_signed_when_sovos_present():
    try:
        from sovos_city.chain import Chain  # noqa
        r = self_measure("signed-agent", COMPLIANT)
        # sovos-city present -> card is signed (crypto available on pod)
        assert r["signed"] is True
    except ImportError:
        pytest.skip("sovos-city not importable in this env")
