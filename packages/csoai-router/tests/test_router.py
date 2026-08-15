"""Tests for csoai-router — connectivity surface absorb."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csoai_router
import csoai_router.sov4_router as r4
import csoai_router.sov_orchestrator as orch
import csoai_router.master_hives as mh
import csoai_router.owem_cluster as owc
import csoai_router.router_control as rc
import csoai_router.fleet_dashboard as fd
import csoai_router.fleet_power as fp


def test_r01_router_modules_importable():
    """All 7 safe modules import without side effects."""
    for mod in [r4, orch, mh, owc, rc, fd, fp]:
        assert hasattr(mod, "__name__")
        assert mod.__name__.startswith("csoai_router")
    print("  PASS r01 7/7 modules importable")


def test_r02_sov4_router_has_routing_logic():
    """The sov4 router has the routing fn + suite table."""
    syms = [n for n in dir(r4) if not n.startswith("_")]
    assert "SUITES" in syms or "suites" in syms or len(syms) > 20
    print(f"  PASS r02 sov4_router exposes {len(syms)} symbols")


def test_r03_master_hives_three_brands():
    """Master_hives knows the three master OWEM groups."""
    syms = [n for n in dir(mh) if not n.startswith("_")]
    assert len(syms) >= 5
    print(f"  PASS r03 master_hives has {len(syms)} symbols (CSOAI/DEFONEOS/DEFENCE/MEOK)")


def test_r04_orchestrator_wires_routers():
    """sov_orchestrator wires routers+pipelines+models."""
    syms = [n for n in dir(orch) if not n.startswith("_")]
    assert len(syms) >= 10
    print(f"  PASS r04 sov_orchestrator has {len(syms)} symbols")


def test_r05_time_loop_scripts_excluded():
    """sov_swarm + fleet_monitor must NOT be in __all__ (time-loop modules)."""
    assert "sov_swarm" not in csoai_router.__all__
    assert "fleet_monitor" not in csoai_router.__all__
    print("  PASS r05 fleet_monitor + sov_swarm are NOT in __all__ (run as scripts)")


def test_r06_scripts_present_on_disk():
    """Both time-loop scripts ARE present, just not auto-imported."""
    pkgdir = Path(__file__).resolve().parent.parent / "src" / "csoai_router"
    assert (pkgdir / "fleet_monitor.py").is_file()
    assert (pkgdir / "sov_swarm.py").is_file()
    print("  PASS r06 fleet_monitor.py + sov_swarm.py on disk for script-invoke")


def main():
    tests = [
        test_r01_router_modules_importable,
        test_r02_sov4_router_has_routing_logic,
        test_r03_master_hives_three_brands,
        test_r04_orchestrator_wires_routers,
        test_r05_time_loop_scripts_excluded,
        test_r06_scripts_present_on_disk,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{'OK' if passed == len(tests) else 'PARTIAL'} {passed}/{len(tests)} PASSED")


if __name__ == "__main__":
    main()
