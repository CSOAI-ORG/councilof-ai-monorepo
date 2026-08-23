#!/usr/bin/env python3
"""data_dao — eunomia data DAO.

Every route on the router generates data: arena traces, gaming behaviour,
compliance incidents, SME cash-flow benchmarks. This module registers each dataset
with provenance + license and provides a marketplace (buy/sell with EUN tokens).
The buyers (regulators free / public good, hedge funds, AI labs) pay for the data;
the MEOK gamers train it.

Measurement, not certification. Datasets carry `not_a_certification` provenance.
"""

DATASETS = {}
_NEXT_ID = [1]


def _id():
    vid = "DS-{:03d}".format(_NEXT_ID[0]); _NEXT_ID[0] += 1
    return vid


def register(name, kind, producer, license="cc0-public-good", price_eun=0.0, not_a_certification=True):
    """Register a dataset with provenance. Returns the DAO record."""
    rec = {
        "id": _id(),
        "name": name,
        "kind": kind,              # arena-traces | gaming-behavior | compliance-incidents | cash-flow | benchmark
        "producer": producer,
        "license": license,
        "price_eun": price_eun,
        "not_a_certification": not_a_certification,
        "sold": 0,
    }
    DATASETS[rec["id"]] = rec
    return rec


def list_all():
    return list(DATASETS.values())


def buy(dataset_id, buyer, eun_balance):
    """Sell a priced dataset for EUN tokens (agents-only; humans never charged)."""
    rec = DATASETS.get(dataset_id)
    if not rec:
        return {"error": "no such dataset"}
    if rec["price_eun"] > eun_balance:
        return {"error": "insufficient EUN", "price_eun": rec["price_eun"], "balance": eun_balance}
    rec["sold"] += 1
    return {"sold": rec, "buyer": buyer, "remaining_eun": eun_balance - rec["price_eun"]}


if __name__ == "__main__":
    import json
    register("arena-2026-08", "arena-traces", "sovereign arena", price_eun=0.0)
    register("compliance-incidents-2026-08", "compliance-incidents", "risk oracle", license="sfr", price_eun=50.0)
    register("meok-behavior-Q3", "gaming-behavior", "MEOK", price_eun=200.0)
    print("DAO:", json.dumps(list_all(), indent=2))
    print("BUY:", buy("DS-002", "hedge-fund", 100))
