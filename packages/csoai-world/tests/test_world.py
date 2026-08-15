"""Smoke test for csoai-world — verify the IWMS substrate loads."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import csoai_world


def test_w01_package_imports():
    """The csoai-world package loads without side effects."""
    # The selective __init__.py uses try/except so missing sub-modules don't fail
    assert hasattr(csoai_world, "self_test")
    print("  PASS w01 csoai-world imports cleanly")


def test_w02_self_test_runs():
    """The self_test() returns the inventory of accessible symbols."""
    result = csoai_world.self_test()
    assert "loaded" in result
    assert "n_accessible" in result
    assert "subpkg_jspace_arithmetic" in result
    assert result["subpkg_jspace_arithmetic"] == "csoai_world.jspace_arithmetic"
    print(f"  PASS w02 self_test: n_accessible={result['n_accessible']} "
          f"subpkg={result['subpkg_jspace_arithmetic']}")


def test_w03_jspace_arithmetic_subpackage():
    """The jspace_arithmetic sub-package is reachable."""
    import csoai_world.jspace_arithmetic as jsa
    # The real surface: Axis, Move, ErrorVector, ties_merge, ...
    assert hasattr(jsa, "Axis")
    assert hasattr(jsa, "Move")
    assert hasattr(jsa, "ties_merge")
    assert hasattr(jsa, "JSpaceRouter")
    print("  PASS w03 jspace_arithmetic sub-package reachable (Axis/Move/ties_merge/JSpaceRouter)")


def test_w04_four_subspaces():
    """The four sub-spaces (g/b/s/j-space) appear in the source tree."""
    pkgdir = Path(csoai_world.__file__).resolve().parent
    expected = ["g_space", "b_space", "soul", "jspace_arithmetic"]
    for name in expected:
        assert (pkgdir / name).is_dir(), f"missing sub-dir: {name}"
    print(f"  PASS w04 sub-space dirs present: {expected}")


def main():
    tests = [
        test_w01_package_imports,
        test_w02_self_test_runs,
        test_w03_jspace_arithmetic_subpackage,
        test_w04_four_subspaces,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
    print(f"\n{'OK' if passed == len(tests) else 'PARTIAL'} "
          f"{passed}/{len(tests)} PASSED")


if __name__ == "__main__":
    main()
