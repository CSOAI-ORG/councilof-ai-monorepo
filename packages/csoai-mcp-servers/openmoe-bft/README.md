# openmoe-bft — STATUS: SCAFFOLD (v0.1.0)

**STATUS:** SCAFFOLD — minimal honest implementation of Byzantine Fault
Tolerant routing for 3-voter council decisions.

## What this scaffold does

Implements a 3-voter BFT consensus where:
1. Each voter casts a (decision, weight) tuple
2. A query is "approved" iff ≥ �2/3⌉ of voters (by total weight) agree
3. Byzatine voters (those disagreeing with the majority) are flagged
4. Returns the consensus + which voters were dissenting

This is the minimal BFT logic the SOVOS "council-of-22" routing uses.
Production version should add: voter reputation tracking, weighted stake,
adaptive quorum thresholds, and persistence.

## License

MIT — CSOAI Ltd (UK 16939677)
