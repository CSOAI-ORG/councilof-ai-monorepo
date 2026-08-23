"""Sanity tests for the csoai-axis-engine package (stdlib-only)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src" / "csoai_axis_engine"))
from gspc_six_axis_e2e import wilson

def test_wilson_full_accuracy():
    p, lo, hi = wilson(10, 10)
    assert abs(p - 1.0) < 1e-9
    assert hi <= 1.0

def test_wilson_zero():
    p, lo, hi = wilson(0, 10)
    assert abs(p - 0.0) < 1e-9

def test_wilson_interval_narrow():
    p, lo, hi = wilson(8, 10)
    assert lo <= p <= hi
    assert lo >= 0.0 and hi <= 1.0

def test_wilson_nan_on_zero_n():
    import math
    p, lo, hi = wilson(0, 0)
    assert math.isnan(p) and math.isnan(lo) and math.isnan(hi)

if __name__ == "__main__":
    test_wilson_full_accuracy(); test_wilson_zero(); test_wilson_interval_narrow(); test_wilson_nan_on_zero_n()
    print("PASS")
