# csoai-engine

**Fixable agentic engine harness** — the beast layer over the 14 GSPC axes.

Every axis becomes an engine:

- `status()` — board gate, bank_items, n_models, signed sha (from the manifests)
- `diagnose()` — the axis's measurable gap (minority-class <30, Art5 coverage <8,
  paraphrase blind spot, precision/recall <0.99, UNMEASURED refusal rate)
- `fix(delta)` — record a bounded fix candidate, re-evaluate the axis's own
  metric, emit a signed before/after record (promotion is an owner decision)

Run on the A100 signing node:

```bash
python3 -m csoai_engine status          # all 14 engines at a glance
python3 -m csoai_engine diagnose        # every axis's gap, one line each
python3 -m csoai_engine diagnose gov
python3 -m csoai_engine fix gov --delta "extend bank +50 items"
```

Honesty: every fix record is Ed25519-signed on the signing node; nothing is
"promoted" without owner sign-off; the honest before/after is always kept.
