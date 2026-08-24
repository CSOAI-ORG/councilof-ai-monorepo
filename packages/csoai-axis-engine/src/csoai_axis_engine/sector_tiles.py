"""Sector tiles — the white-label kit applied to each end party (SOVOS Part IX).

regulators (R8 free) · insurers · bond desks · COBOL · every party gets the
verifiable measurement surface branded to THEM; the trust root (signer) never
white-labels. Each tile maps the sector to its EUNOMIA axes + the Article exposure.
"""
from __future__ import annotations

SECTOR_TILES = {
  "regulator":    {"name": "Regulator", "axes": ["governance", "provenance", "conformance"], "lane": "R8-free", "anchor": "public watchdog",
                   "article_exposure": ["art5", "art6", "art13", "art14", "art15", "art50"]},
  "insurer":      {"name": "Insurance", "axes": ["insurance", "privacy-risk"], "lane": "x402-data", "anchor": "underwriting / claims / fraud",
                   "article_exposure": ["art9", "art14"]},
  "bond-desk":    {"name": "Bond market", "axes": ["bond-router", "climate-transition"], "lane": "x402-data", "anchor": "A2A bond settlement attestation",
                   "article_exposure": ["art6", "art8", "art9", "art15"]},
  "cobol":        {"name": "COBOL legacy", "axes": ["bond-router"], "lane": "x402-data", "anchor": "COPYBOOK -> A2A attestation",
                   "article_exposure": ["art8", "art11"]},
  "vendor":       {"name": "AI vendor", "axes": ["governance", "openness", "care"], "lane": "x402-data", "anchor": "self-audit before contact",
                   "article_exposure": ["art5", "art6", "art13", "art14", "art15", "art50", "art51"]},
}


def sector_tile(sector: str) -> dict:
    from csoai_axis_engine.eu_ai_act_crosswalk import crosswalk
    t = SECTOR_TILES[sector]
    return {"sector": t["name"], "axes": t["axes"], "lane": t["lane"], "anchor": t["anchor"],
            "article_exposure": t["article_exposure"], "map_articles": crosswalk(t["anchor"], t["axes"])}


def all_sector_tiles() -> dict:
    return {k: {"name": v["name"], "axes": v["axes"], "lane": v["lane"], "anchor": v["anchor"]} for k, v in SECTOR_TILES.items()}


if __name__ == "__main__":
    import json
    print(json.dumps(all_sector_tiles(), indent=2))
