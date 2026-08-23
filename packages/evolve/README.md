# evolve

**The 90/10 router as a frozen split-conformal predicate** — the crown-jewel gate
of the COAI self-improving loop. Deterministic, distribution-free, **no
LLM-as-judge**. Once a threshold is frozen from a calibration set, every routing
and promotion decision is pure arithmetic and exactly reproducible.

Dependency-light: **numpy only**. No ML framework.

See [`SPEC.md`](./SPEC.md) for the full mechanism (MAPE-K placement, the coverage
sandwich, Conformal Risk Control, safeguards, and the BUILT-vs-GAP line).

## Install & test

```bash
pip install -e ".[test]"
pytest            # 70 passed
```

## Quickstart

```python
from evolve import calibrate, Router, promote_if_better
from evolve import EnsembleDisagreement

# 1) Score items with a pluggable, deterministic nonconformity score.
score_fn = EnsembleDisagreement()          # variance/entropy across a decorrelated ensemble

# 2) Freeze the 90/10 threshold on a held-out calibration set (alpha=0.10 -> ~90% auto).
q_hat  = calibrate(calib_scores, alpha=0.10)
router = Router(q_hat, alpha=0.10, n_calib=len(calib_scores))

# 3) Route — a pure comparison, no model judges a model.
router.decide(score_fn(item))              # -> "auto" | "escalate"

# 4) Promote a candidate only if it beats the frozen baseline with the correct
#    sign AND by at least min_effect (guards the -9.16 wrong-sign bug).
promote_if_better(candidate_metrics, baseline_metrics,
                  min_effect=1.0, significance=0.05)   # -> bool
```

## Guarantee

For continuous (no-tie) nonconformity scores, the frozen threshold `q̂` gives the
finite-sample, distribution-free coverage sandwich

```
1 - alpha  <=  P(score_test <= q_hat)  <=  1 - alpha + 1/(n+1)
```

verified empirically in the test suite across normal / exponential / uniform
score distributions, several `alpha`, and several `n`.

## API

| Symbol | Stage | Purpose |
|---|---|---|
| `calibrate(scores, alpha)` | Analyze | frozen split-conformal threshold `q̂` |
| `coverage_bounds(n, alpha)` | — | the finite-sample sandwich `(lower, upper)` |
| `route(score, q_hat)` / `Router` | Analyze | the frozen 90/10 predicate |
| `calibrate_risk(losses, alpha, b=…)` | Analyze | Conformal Risk Control: `E[L] ≤ α` |
| `select_risk_threshold(...)` | Analyze | loosest threshold controlling risk |
| `EnsembleDisagreement` *(rec.)*, `OneMinusMaxSoftmax`, `DistanceToCalibration` | Analyze | pluggable nonconformity scores |
| `promote_if_better(...)` / `promote_report(...)` | Execute | sign-guarded, significance-tested promote-gate |

## License

Apache-2.0.
