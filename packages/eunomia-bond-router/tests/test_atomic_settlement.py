#!/usr/bin/env python3
"""test_atomic_settlement — prove the atomic DvP module all-or-nothing."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_bond_router.atomic_settlement import settle
from eunomia_bond_router.cobol_parser import parse_copybook, parse_record


def test_atomic_settles():
    r = settle({
        "bond": {"quantity": 1000000, "currency": "USD", "owner": "buyer"},
        "cash": {"quantity": 1025000, "currency": "USD", "owner": "seller"},
    })
    assert r["verified"]["all_ok"] is True
    assert r["outcome"]["status"] == "settled"


def test_atomic_refunds_both():
    # cash leg missing -> all-or-nothing -> no release
    r = settle({
        "bond": {"quantity": 1000000, "currency": "USD", "owner": "buyer"},
        "cash": {"quantity": 0, "currency": "USD", "owner": "seller"},
    })
    assert r["verified"]["all_ok"] is False
    assert r["outcome"]["status"] == "not-settled"


def test_atomic_compliance_gate_blocks():
    r = settle({
        "bond": {"quantity": 1000000, "currency": "USD", "owner": "buyer"},
        "cash": {"quantity": 1025000, "currency": "USD", "owner": "seller"},
    }, compliance=False)
    assert r["verified"]["all_ok"] is False
    assert r["outcome"]["status"] == "not-settled"


def test_atomic_parses_copybook_and_settles():
    layout = parse_copybook("01 SETTLEMENT-RECORD.\n 05 NOTIONAL PIC 9(12)V99.\n 05 CCY PIC X(3).")
    rec = parse_record("00000000012345USD", layout)  # 14-char notional (12 int + 2 dec) + 3-char CCY
    assert rec["notional"] == 123.45, rec
    r = settle({"bond": {"quantity": rec["notional"], "currency": rec["ccy"], "owner": "buyer"},
                "cash": {"quantity": rec["notional"], "currency": rec["ccy"], "owner": "seller"}})
    assert r["outcome"]["status"] == "settled"


if __name__ == "__main__":
    test_atomic_settles(); print("ok: atomic settles")
    test_atomic_refunds_both(); print("ok: atomic refunds both")
    test_atomic_compliance_gate_blocks(); print("ok: compliance gate blocks")
    test_atomic_parses_copybook_and_settles(); print("ok: copybook -> settled")
    print("ALL ATOMIC SETTLEMENT TESTS PASS")
