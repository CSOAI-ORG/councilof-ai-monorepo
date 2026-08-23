#!/usr/bin/env python3
"""test_crosswalk — eunomia east-west bridge."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_east_west_bridge.crosswalk import crosswalk, map_all


def test_tc260_maps():
    r = crosswalk("tc260-registry")
    assert r["matched"] == "tc260-registry"
    assert r["output_kind"] == "governance-score"


def test_map_all_complete():
    m = map_all()
    assert len(m) >= 5
    # every known signal resolves (no None output)
    for v in m.values():
        assert v["west_output"], v


def test_unmapped_honest():
    r = crosswalk("unknown-east-signal")
    assert r["matched"] is None
    assert "never interpolate" in r["note"]


if __name__ == "__main__":
    test_tc260_maps(); print("ok: tc260 maps")
    test_map_all_complete(); print("ok: map all complete")
    test_unmapped_honest(); print("ok: unmapped honest")
    print("ALL EAST-WEST TESTS PASS")
