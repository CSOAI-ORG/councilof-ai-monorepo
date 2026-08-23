# eunomia-east-west-bridge

Bridge 3 — the **corpus callosum**. China's TC260 ↔ EU AI Act ↔ NIST RMF ↔ UK DSIT
don't talk to each other. `crosswalk.py` maps an East governance signal to a West
output (NIST RMF score, GDPR-anonymised identity, EU AI Act framing) so a Chinese
insurer can underwrite a UK SME because both trust the CSOAI attestation.

`crosswalk()` is a deterministic translation table (never interpolates; unmapped
signals are reported honestly).

> Measurement, not certification. Deterministic, offline.

## Test
```
python3 tests/test_crosswalk.py
```
