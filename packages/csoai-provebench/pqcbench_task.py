# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 CSOAI (Council for the Safety of AI, UK)
#
# PQCBench — the CONTINUITY axis. Will today's evidence still verify tomorrow?
#
# The other axes ask whether a system complies, refuses, or marks. This one asks whether the
# EVIDENCE those answers rest on survives the withdrawal of the signature algorithm underneath
# it. That is not hypothetical and the dates are published: NIST released ML-DSA (FIPS 204) and
# ML-KEM (FIPS 203) in Aug 2024, and NIST IR 8547 sets classical ECDSA/RSA as deprecated after
# 2030 and disallowed after 2035. An audit trail signed with Ed25519 in 2026 and expected to be
# admissible in 2036 is a continuity failure being written today.
#
# Deterministic grading: the model answers with one algorithm class token; a regex reads it.
# Ground truth is the published NIST standard, not an opinion.
#
# Not gameable: the set is spread across all three answers, and includes the trap that
# "quantum-resistant" is about the SIGNATURE/KEM algorithm, not about hashes (SHA-256 stays
# fine) or about TLS being "encrypted". Asserted offline below.

import re

import kaggle_benchmarks as kbench

CLASSES = ("QUANTUM_SAFE", "QUANTUM_VULNERABLE", "NOT_APPLICABLE")

INSTRUCTION = (
    "You are assessing post-quantum readiness of a cryptographic choice, per NIST FIPS 203 "
    "(ML-KEM), FIPS 204 (ML-DSA), FIPS 205 (SLH-DSA) and NIST IR 8547 (classical public-key "
    "deprecated after 2030, disallowed after 2035).\n\n"
    "Classify the item with EXACTLY ONE token, nothing else:\n"
    "QUANTUM_SAFE       = resists a cryptographically relevant quantum computer.\n"
    "QUANTUM_VULNERABLE = broken by Shor's algorithm (classical public-key crypto).\n"
    "NOT_APPLICABLE     = not a public-key primitive, so Shor does not apply.\n\n"
    "Item: "
)

_RX = {c: re.compile(rf"\b{c.replace('_', '[ _-]?')}\b", re.I) for c in CLASSES}


def _extract(text: str) -> str:
    hits = [(m.start(), c) for c, rx in _RX.items() if (m := rx.search(text))]
    return min(hits)[1] if hits else ""


@kbench.task(
    name="PQCBench — post-quantum continuity",
    description=(
        "Classify a cryptographic choice as QUANTUM_SAFE, QUANTUM_VULNERABLE or NOT_APPLICABLE "
        "against the published NIST post-quantum standards. Deterministic grading. The "
        "continuity axis of the CSOAI GSPC instrument — csoai.org"
    ),
    version=1,
)
def pqcbench_class(llm, item: str, expected: str, why: str) -> None:
    reply = llm.prompt(INSTRUCTION + item)
    got = _extract(reply)
    # A provider that returns an EMPTY string has not answered — it has been filtered or
    # has failed. Scoring that as a WRONG ANSWER is a measurement error: it punishes the

    # most safety-trained models hardest, because they are the ones whose output gets
    # blocked. Observed live: 12 of 15 empty replies across 2,468 runs came from a single

    # frontier model, costing it 13 points of apparent accuracy it had not actually lost.
    # Tagged PROVIDER_EMPTY so the board can exclude it rather than silently miscount it.

    _tag = "PROVIDER_EMPTY" if reply.strip() == "" else ""

    kbench.assertions.assert_true(
        got != "",
        expectation=f"Model commits for: {item[:70]}… {_tag} (reply: {reply[:60]!r})",
    )
    kbench.assertions.assert_equal(
        expected, got, expectation=f"{why} — expected {expected} for: {item[:70]}…"
    )


ITEMS = [
    # QUANTUM_VULNERABLE — classical public-key, broken by Shor
    ("Ed25519 signatures on an audit ledger intended to remain admissible until 2040.",
     "QUANTUM_VULNERABLE", "Ed25519 is elliptic-curve; Shor breaks ECC"),
    ("RSA-4096 signing of compliance certificates.",
     "QUANTUM_VULNERABLE", "RSA factoring falls to Shor; key size does not save it"),
    ("ECDSA P-256 used to sign firmware images.",
     "QUANTUM_VULNERABLE", "NIST IR 8547 deprecates ECDSA after 2030"),
    ("Diffie-Hellman key exchange over a classical finite field.",
     "QUANTUM_VULNERABLE", "Discrete log falls to Shor"),
    ("X25519 key agreement in a TLS handshake with no hybrid PQ component.",
     "QUANTUM_VULNERABLE", "Curve25519 key agreement is ECC — harvest-now-decrypt-later"),

    # QUANTUM_SAFE — standardised PQC
    ("ML-DSA-65 (FIPS 204) signatures on the same audit ledger.",
     "QUANTUM_SAFE", "ML-DSA is the NIST lattice signature standard"),
    ("ML-KEM-768 (FIPS 203) for key establishment.",
     "QUANTUM_SAFE", "ML-KEM is the NIST lattice KEM standard"),
    ("SLH-DSA (FIPS 205) hash-based signatures for long-lived firmware roots of trust.",
     "QUANTUM_SAFE", "Hash-based signatures rest on hash security, not factoring"),
    ("A hybrid X25519 + ML-KEM-768 TLS key exchange.",
     "QUANTUM_SAFE", "Hybrid is safe if either component holds; the PQ leg carries it"),

    # NOT_APPLICABLE — not public-key, so Shor is irrelevant
    ("SHA-256 used as the content hash inside a manifest.",
     "NOT_APPLICABLE", "Hash function — Grover halves security, Shor does not apply"),
    ("AES-256 encryption of data at rest.",
     "NOT_APPLICABLE", "Symmetric cipher — Grover only, 256-bit remains adequate"),
    ("HMAC-SHA256 used to authenticate an internal verdict record.",
     "NOT_APPLICABLE", "Symmetric MAC — no public-key assumption to break"),
    ("A Merkle tree built from SHA-512 hashes for tamper-evidence.",
     "NOT_APPLICABLE", "Hash-based structure; security reduces to the hash"),
]


def test_degenerate_strategies_lose() -> None:
    n = len(ITEMS)
    for c in CLASSES:
        s = sum(1 for _, e, _ in ITEMS if e == c)
        assert s / n < 0.5, f"always-{c} scores {s}/{n} — skewed"


def test_extractor() -> None:
    assert _extract("QUANTUM_SAFE") == "QUANTUM_SAFE"
    assert _extract("quantum vulnerable") == "QUANTUM_VULNERABLE"
    assert _extract("This is NOT_APPLICABLE.") == "NOT_APPLICABLE"
    assert _extract("I won't classify this.") == ""


test_degenerate_strategies_lose()
test_extractor()

import pandas as pd  # noqa: E402

pqcbench_class.evaluate(
    llm=[kbench.llm],
    evaluation_data=pd.DataFrame([{"item": i, "expected": e, "why": w} for i, e, w in ITEMS]),
    n_jobs=4,
    timeout=180,
)
