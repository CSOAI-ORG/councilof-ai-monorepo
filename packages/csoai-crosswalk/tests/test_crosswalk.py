"""Tests for csoai-crosswalk — the regulation-manifold atlas engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from csoai_crosswalk import (
    BUILTIN_EUAI, ControlRow, CrosswalkAtlas,
    align_cost, builtin_euai_atlas, from_cellar_docs, load_crosswalk_json,
    obstruction_set, self_test,
)


def test_cw01_builtin_has_real_content():
    """The builtin EU AI Act atlas has 13 articles, 26 rows, 2 frameworks."""
    eu = builtin_euai_atlas()
    assert len(BUILTIN_EUAI) == 13
    assert eu.controls_covered() == 26  # 13 x (NIST + ISO)
    assert "NIST-AI-RMF" in eu.target_frameworks()
    assert "ISO-42001" in eu.target_frameworks()
    print(f"  ✅ builtin atlas: 13 articles, 26 rows, frameworks={eu.target_frameworks()}")


def test_cw02_full_overlap_no_obstruction():
    """Two atlases mapping the same locals to the same framework → 0 obstructed."""
    eu = builtin_euai_atlas()
    nist = CrosswalkAtlas(name="NIST")
    for local, nist_c, iso_c in BUILTIN_EUAI:
        nist.add(local, nist_c, "NIST-AI-RMF")
    res = obstruction_set(eu, nist)
    # EU has rows for NIST (locals Art5..AnnexIII) and ISO (same locals) —
    # but obstruction_set compares LOCAL sets; both have all 13.
    assert res["n_shared"] == 13
    assert res["n_obstructed"] == 0
    assert res["shared_ratio"] == 1.0
    print(f"  ✅ full shared core: ratio={res['shared_ratio']}, "
          f"obstructed={res['n_obstructed']}")


def test_cw03_partial_overlap_obstruction():
    """A vendor covering only 5/13 locals → 8 obstructed (the counsel workload)."""
    eu = builtin_euai_atlas()
    vend = CrosswalkAtlas(name="vendor")
    for local, nist_c, iso_c in BUILTIN_EUAI:
        if local in {"Art5", "Art9", "Art10", "Art14", "Art15"}:
            vend.add(local, "CTRL-" + nist_c, "VENDOR")
    res = obstruction_set(eu, vend)
    assert res["n_shared"] == 5
    assert res["n_obstructed"] == 8
    assert res["shared_ratio"] < 0.5
    assert "Art50" in res["obstructed_locals"]  # ANSI/Art50 not covered → obstruction
    print(f"  ✅ partial: shared={res['n_shared']}, "
          f"obstructed={res['n_obstructed']}, ratio={res['shared_ratio']}")


def test_cw04_align_cost_inverse_of_shared():
    """align_cost = 1 - shared_ratio; full share → 0, sparse → high."""
    eu = builtin_euai_atlas()
    nist = CrosswalkAtlas(name="NIST")
    for local, nist_c, iso_c in BUILTIN_EUAI:
        nist.add(local, nist_c, "NIST-AI-RMF")
    vend = CrosswalkAtlas(name="vendor")
    for local, nist_c, iso_c in BUILTIN_EUAI:
        if local in {"Art5", "Art9", "Art10", "Art14", "Art15"}:
            vend.add(local, "X", "VENDOR")
    assert align_cost(eu, nist) == 0.0
    assert align_cost(eu, vend) > 0.5
    print(f"  ✅ align_cost: full={align_cost(eu, nist)}, "
          f"sparse={align_cost(eu, vend)}")


def test_cw05_chain_id_deterministic():
    """obstruction chain_id is 24 hex, deterministic for same inputs."""
    eu = builtin_euai_atlas()
    iso = CrosswalkAtlas(name="ISO")
    for local, nist_c, iso_c in BUILTIN_EUAI[:9]:
        iso.add(local, iso_c, "ISO-42001")
    r1 = obstruction_set(eu, iso)
    r2 = obstruction_set(eu, iso)
    assert r1["chain_id"] == r2["chain_id"]
    assert len(r1["chain_id"]) == 24
    print(f"  ✅ obstruction chain_id is 24-char hex, deterministic")


def test_cw06_load_crosswalk_json():
    """load_crosswalk_json ingests external structured data."""
    data = [
        {"local": "A1", "target": "C1", "target_framework": "NIST"},
        {"local": "A2", "target": "C2", "target_framework": "ISO"},
    ]
    atlas = load_crosswalk_json(data)
    assert atlas.controls_covered() == 2
    assert atlas.target_frameworks() == ["ISO", "NIST"]
    print(f"  ✅ load_crosswalk_json: 2 rows, frameworks={atlas.target_frameworks()}")


def test_cw07_iso_subset_obstruction():
    """ISO covering 9/13 locals → 4 obstructed (the classic divergent third)."""
    eu = builtin_euai_atlas()
    iso = CrosswalkAtlas(name="ISO")
    for local, nist_c, iso_c in BUILTIN_EUAI[:9]:
        iso.add(local, iso_c, "ISO-42001")
    res = obstruction_set(eu, iso)
    assert res["n_shared"] == 9
    assert res["n_obstructed"] == 4
    print(f"  ✅ ISO subset: shared={res['n_shared']}, "
          f"obstructed={res['n_obstructed']} (the classic 2/3 shared core)")


def test_cw08_controlrow_dataclass():
    """ControlRow is a clean dataclass."""
    r = ControlRow("Art14", "GOVERN-2.2", "NIST-AI-RMF")
    assert r.local == "Art14"
    assert r.target == "GOVERN-2.2"
    assert r.target_framework == "NIST-AI-RMF"
    print(f"  ✅ ControlRow dataclass: {r.to_dict()}")


def test_cw09_self_test():
    """self_test returns a complete, sensible picture."""
    info = self_test()
    assert info["rows_eu"] == 26
    assert info["iso_shared_ratio"] > 0.6   # ISO covers 9/13 ~ 0.69
    assert info["iso_obstructed"] == 4
    assert info["vendor_obstructed"] == 8
    assert info["chain_id_len"] == 24
    print(f"  ✅ self_test: iso_ratio={info['iso_shared_ratio']}, "
          f"iso_obstructed={info['iso_obstructed']}, "
          f"vendor_obstructed={info['vendor_obstructed']}")


def test_cw10_empty_atlas():
    """An empty atlas → zero shared, zero obstructed, ratio 0."""
    a = CrosswalkAtlas(name="empty")
    eu = builtin_euai_atlas()
    res = obstruction_set(a, eu)
    assert res["n_shared"] == 0
    assert res["n_obstructed"] == 0
    print(f"  ✅ empty atlas: shared=0, obstructed=0")


def test_cw11_from_cellar_docs_seeds_atlas():
    """CELLAR LawDocuments seed an atlas (jurisdiction-as-clan loop)."""
    class Doc:
        def __init__(self, celex, itype, year):
            self.celex = celex
            self.instrument_type = itype
            self.publication_year = year
    docs = [
        Doc("32024R1689", "Regulation", 2024),   # AI Act
        Doc("32016R0679", "Regulation", 2016),   # GDPR
        Doc("32022L2555", "Directive", 2022),    # NIS2
    ]
    atlas = from_cellar_docs(docs)
    assert atlas.name == "cellar-jurisdiction"
    assert atlas.source == "cellar"
    assert atlas.controls_covered() == 3
    # The CELEX is the local (regulation-as-task-vector identity)
    locals_set = {r.local for r in atlas.rows}
    assert "32024R1689" in locals_set
    print(f"  ✅ Cellar docs → atlas: 3 regulations, CELEX as local")


def test_cw12_cellar_atlas_obstruction_with_builtin():
    """Obstruction math runs against a Cellar-derived chart."""
    class Doc:
        def __init__(self, celex, itype, year):
            self.celex = celex
            self.instrument_type = itype
            self.publication_year = year
    cellar = from_cellar_docs([
        Doc("32024R1689", "Regulation", 2024),
    ])
    eu = builtin_euai_atlas()
    res = obstruction_set(eu, cellar)
    # The builtin atlas has 13 unique article locals (Art5…) that don't
    # match CELEX strings, so all 13 obstruct — the sheaf-structure is
    # computed over unique locals, not row count.
    assert res["n_obstructed"] == 13
    assert res["n_shared"] == 0
    assert res["chain_id"] and len(res["chain_id"]) == 24
    print(f"  ✅ Cellar vs builtin: obstruction set computed ({res['n_obstructed']} locals obstructed)")


if __name__ == "__main__":
    tests = [
        test_cw01_builtin_has_real_content,
        test_cw02_full_overlap_no_obstruction,
        test_cw03_partial_overlap_obstruction,
        test_cw04_align_cost_inverse_of_shared,
        test_cw05_chain_id_deterministic,
        test_cw06_load_crosswalk_json,
        test_cw07_iso_subset_obstruction,
        test_cw08_controlrow_dataclass,
        test_cw09_self_test,
        test_cw10_empty_atlas,
        test_cw11_from_cellar_docs_seeds_atlas,
        test_cw12_cellar_atlas_obstruction_with_builtin,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            import traceback; traceback.print_exc()
            print(f"  ❌ FAIL {t.__name__}: {e}")
    print(f"\n{'✅' if passed == len(tests) else '❌'} {passed}/{len(tests)} PASSED")
