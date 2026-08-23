# eunomia-insurance-engine

Bridge 2 (Open) — the **risk ↔ capital** lymphatic system. Banks want to lend;
insurers want to avoid risk. The friction between them is the pricing signal.

`risk_probe.py` runs a **care-membrane-inspired ethics + risk probe** (deterministic,
no LLM) over a policy/risk description and returns an underwriting recommendation
(`insure` / `flag` / `decline`) + a quoteable, signed-attestable scorecard.

> Measurement, not certification. Deterministic, offline.

## Route
```
eunomia://sector/insurance  (live /api/attest sector-agnostic)
```

## Test
```
python3 tests/test_risk_probe.py
```
