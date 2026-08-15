# sov33-benchmark — STATUS: SCAFFOLD (v0.1.0)

**STATUS:** SCAFFOLD — minimal honest implementation of the SOV33 governance
benchmark runner. The full 479-item GovBench corpus needs to be migrated
from the original source.

## What this scaffold does

Implements the canonical GovBench loader and scoring engine:
1. Load governance items from a JSONL file
2. For each item, run a model query (or use the SOV SIGNAL API)
3. Score the response on the 13-axis rubric
4. Aggregate into a per-item score + per-axis SOV SIGNAL

The scaffold ships with 3 demo items (EU AI Act Article 5, NIST RMF GOVERN-1.1,
ISO 42001 Clause 5.2) so the runner is testable end-to-end. Add the full
479-item corpus by copying `data/govbench-479.jsonl` into the package.

## License

MIT — CSOAI Ltd (UK 16939677)
