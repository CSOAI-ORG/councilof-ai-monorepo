#!/usr/bin/env python3
"""crosswalk — eunomia east-west bridge.

China's TC260 <-> EU AI Act <-> NIST RMF <-> UK DSIT. They don't talk to each other.
This module is the corpus callosum: it maps an East (China/TC260) governance signal
to a West output (NIST RMF score, GDPR-anonymised identity, EU AI Act framing),
so a Chinese insurer can underwrite a UK SME because both trust the CSOAI attestation.

Measurement, not certification. Deterministic translation table, no LLM.
"""

# East signal -> West output mapping (a real, curated crosswalk, not guesses).
CROSSWALK = {
    "tc260-registry": {
        "east": "TC260 algorithm registry (China AI governance)",
        "west": "NIST AI RMF / EU AI Act high-risk dossier",
        "output": "governance-score",
    },
    "social-credit-profile": {
        "east": "China social credit / behaviour profile",
        "west": "GDPR-anonymised verifiable identity (did:web:csoai.org)",
        "output": "identity",
    },
    "pdca-cycle": {
        "east": "PDCA (Plan-Do-Check-Act)",
        "west": "Agile sprint + on-chain attestation (proofof-ai)",
        "output": "lifecycle",
    },
    "algorithm-filing": {
        "east": "TC260 algorithm filing (registration)",
        "west": "EU AI Act Art 5 / NIST RMF mapping",
        "output": "compliance-crosswalk",
    },
    "data-localisation": {
        "east": "China data localisation (PIPL)",
        "west": "EU data adequacy + GDPR minimalisation",
        "output": "data-flow",
    },
}


def crosswalk(signal):
    """Map an East governance signal to its West output + translation."""
    key = (signal or "").lower().replace(" ", "-").replace("_", "-")
    if key in CROSSWALK:
        e = CROSSWALK[key]
        return {
            "east_signal": signal,
            "matched": key,
            "east": e["east"],
            "west_output": e["west"],
            "output_kind": e["output"],
            "trust": "both trust the CSOAI attestation, not each other",
        }
    return {"east_signal": signal, "matched": None, "east": None, "west_output": None, "output_kind": None,
            "note": "unmapped signal — report honestly, never interpolate"}


def map_all():
    """Crosswalk every known East signal -> West output (the full pipe)."""
    return {k: crosswalk(k) for k in CROSSWALK}


if __name__ == "__main__":
    import json
    print("EAST->WEST:", json.dumps(map_all(), indent=2))
