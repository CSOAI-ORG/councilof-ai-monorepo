#!/usr/bin/env python3
"""a2a_card — emit an A2A agent card for the bond router (the agent's identity)."""
import json

def agent_card(name="eunomia-bond-router", desc="COBOL->A2A bond bridge; parses COPYBOOK, attests records, maps DIDs"):
    return {
        "name": name, "description": desc,
        "assertions": ["reads COBOL COPYBOOK", "emits attestable JSON",
                       "signed ed25519 did:web:csoai.org#estate-chain-1",
                       "bridges bonds/insurance/stocks/East-West under one measurement frame"],
        "capabilities": ["cobol-parse", "record-attest", "did-mapping", "care-membrane-scoring"],
        "verifiable": True,
    }
