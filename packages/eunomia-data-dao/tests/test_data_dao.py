#!/usr/bin/env python3
"""test_data_dao — eunomia data DAO."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from eunomia_data_dao.data_dao import register, list_all, buy


def test_register_and_list():
    register("arena-2026-08", "arena-traces", "sovereign arena", price_eun=0.0)
    register("meok-behavior-Q3", "gaming-behavior", "MEOK", price_eun=200.0)
    assert len(list_all()) == 2
    assert all(d["not_a_certification"] for d in list_all())


def test_sell_priced():
    d = register("incidents", "compliance-incidents", "risk oracle", license="sfr", price_eun=50.0)
    r = buy(d["id"], "hedge-fund", 100)
    assert "sold" in r and r["sold"]["sold"] == 1
    assert r["remaining_eun"] == 50.0


def test_sell_insufficient():
    d = register("expensive", "benchmark", "lab", price_eun=500.0)
    r = buy(d["id"], "poor-buyer", 10)
    assert r["error"] == "insufficient EUN"


if __name__ == "__main__":
    test_register_and_list(); print("ok: register + list")
    test_sell_priced(); print("ok: sell priced")
    test_sell_insufficient(); print("ok: sell insufficient")
    print("ALL DATA DAO TESTS PASS")
