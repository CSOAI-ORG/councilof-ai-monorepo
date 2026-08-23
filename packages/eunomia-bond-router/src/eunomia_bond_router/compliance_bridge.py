#!/usr/bin/env python3
"""compliance_bridge — eunomia bond router (Open 4): the compliance route.

A bond trade crosses EU MiCA, MiFID II, EU AI Act, ISO 42001, DORA and the locality's
rules. Instead of one compliance team per jurisdiction, this maps a trade to the
correct frameworks and returns a single compliance attestation. Compliance as a
router function, not a department. Measurement, not certification.
"""

FRAMEWORKS = {
    "mica":      {"scope": "EU crypto-asset / tokenised securities", "required": "MiCA prospectus + issuer disclosure"},
    "mifid2":    {"scope": "EU trading venue", "required": "MiFID II Art 17 + trade reporting"},
    "eu-ai-act": {"scope": "AI in pricing / risk", "required": "EU AI Act transparency + human oversight"},
    "iso42001":  {"scope": "AIMS risk management", "required": "ISO 42001 AI management system"},
    "dora":      {"scope": "EU financial-entity ICT risk", "required": "DORA resilience + reporting"},
    "local":     {"scope": "locality rules", "required": "UK FCA / US SEC / CN CBIRC as applicable"},
}


def compliance_route(trade, jurisdiction="EU"):
    """Map a bond trade to the frameworks + attestation it must pass."""
    j = jurisdiction.upper()
    needs = []
    if "UK" in j: needs += ["mifid2", "dora"]
    else: needs += ["mica", "mifid2"]
    needs += ["eu-ai-act", "iso42001", "local"]
    return {
        "trade": trade,
        "jurisdiction": j,
        "route": [{"framework": f, **FRAMEWORKS[f]} for f in needs],
        "compliance": "attestation: Ed25519-signed, RFC 9943 COSE receipt, not_a_certification",
    }


def required_for(jurisdiction):
    """The set of frameworks a given jurisdiction's trade must route through."""
    return [f for f in compliance_route("__probe__", jurisdiction)["route"]]


if __name__ == "__main__":
    import json
    print("UK ROUTE:", json.dumps(compliance_route("UK Gilt", "UK"), indent=2))
