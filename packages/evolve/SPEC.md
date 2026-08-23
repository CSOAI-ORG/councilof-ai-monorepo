# `evolve` — SPEC

**The 90/10 router as a frozen split-conformal predicate.** The crown-jewel gate
that makes the COAI self-improving loop *compound* instead of drift. Deterministic,
distribution-free, **no LLM-as-judge**: once a threshold is frozen from a
calibration set, every routing and promotion decision is pure arithmetic and
exactly reproducible.

---

## 1. Why a conformal predicate, not a judge

A self-improving loop that grades itself with a model — "ask a big model whether
the small model's answer is good enough" — has no guarantee and a circular
failure mode: the judge and the optimizer share blind spots, so errors compound
silently. Split conformal replaces the judge with a **frozen scalar comparison**
that carries a finite-sample, distribution-free coverage guarantee. The model
never judges the model; a nonconformity *score* is computed, compared to a frozen
threshold `q̂`, and that is the whole decision.

- **Deterministic:** same `(score, q̂)` → same decision, forever.
- **Distribution-free:** the coverage guarantee holds for *any* continuous score
  distribution, with no modelling assumption.
- **Finite-sample:** the guarantee holds at the `n` you actually calibrated on,
  not asymptotically.

---

## 2. The MAPE-K loop and where each piece sits

`evolve` is the decision spine of a five-stage **MAPE-K** autonomic loop
(Monitor–Analyze–Plan–Execute–Knowledge; IBM 2003, *An Architectural Blueprint
for Autonomic Computing*). MAPE-K is the standard reference architecture for
self-managing systems and maps cleanly onto a self-improving model estate:

| Stage | Role | `evolve` component |
|---|---|---|
| **Monitor** | Collect raw findings from the running estate (outputs, ensemble member disagreements, features). | *(external)* feeds the nonconformity scores |
| **Analyze** | Decide, per item, auto-proceed vs escalate. | **`calibrate` → `Router` / `route`** (§3), scores in `scores.py` (§5) |
| **Plan** | Propose a candidate improvement (e.g. a QLoRA adapter) from the escalated slice. | *(external optimizer)* |
| **Execute** | Promote the candidate **only if** it beats the frozen baseline with statistical significance and the correct sign. | **`promote_if_better` / `promote_report`** (§6) |
| **Knowledge** | Append the frozen `q̂`, calibration provenance, and promote verdict to a signed, append-only archive. | **signed-receipts / did:web** tie-in (§7) |

The router sits in **Analyze**. The promote-gate sits in **Execute**. The frozen
thresholds and verdicts are the **Knowledge** the loop accumulates — and because
they are frozen scalars with recorded provenance, the Knowledge base is
*auditable*, which is what lets the loop compound safely.

```
        Monitor ──▶ Analyze ──▶ Plan ──▶ Execute ──▶ (promote?) ──┐
           ▲        (router)            (promote-gate)            │
           │                                                       ▼
           └──────────────── Knowledge (signed, append-only) ◀────┘
                    frozen q̂ + calib provenance + promote verdict
```

---

## 3. The 90/10 router (Analyze)

Calibrate at target miscoverage `α` (e.g. `α = 0.10` → route ≈ 90 % to `auto`):

```python
from evolve import calibrate, Router
q_hat  = calibrate(calib_scores, alpha=0.10)      # frozen threshold
router = Router(q_hat, alpha=0.10, n_calib=len(calib_scores))
router.decide(score)   # -> "auto" (score <= q_hat) | "escalate"
```

`calibrate` returns the `⌈(n+1)(1−α)⌉`-th smallest calibration score (1-indexed,
index clipped to `n`; `+inf` when the index exceeds `n`, i.e. accept-everything
when `n` is too small to certify a finite threshold). `route` is the pure
predicate `score <= q̂ → "auto"`.

**Finite-sample coverage sandwich** (continuous, no-tie scores):

```
1 − α  ≤  P(score_test ≤ q̂)  ≤  1 − α + 1/(n+1)
```

(Vovk, Gammerman & Shafer 2005; Angelopoulos & Bates 2021, arXiv:2107.07511.)
Ties only *raise* coverage, so the lower bound always holds. The upper bound is
what stops the gate being needlessly conservative. This sandwich is verified
empirically in the test suite across three distributions, several `α`, several
`n` (§8).

---

## 4. Conformal Risk Control (Analyze, error-rate mode)

Coverage is a 0/1 miscoverage loss. To calibrate the escalation threshold to a
**target error rate** for any *monotone* loss, use Conformal Risk Control
(Angelopoulos, Bates, Fisch, Lei, Schuster 2022, arXiv:2208.02814). CRC
guarantees `E[L] ≤ α` via the certified quantity

```
E[L_test]  ≤  (n/(n+1)) · mean(calib_losses)  +  b/(n+1)          (loss ≤ b)
```

`calibrate_risk(calib_losses, alpha, b=…)` returns that certified bound;
`select_risk_threshold(...)` searches a monotone loss grid and returns the
**loosest** threshold whose certified risk stays `≤ α` (maximise the `auto`
rate subject to a hard cap on admitted error). CRC controls the *expected* loss
marginally — a mean over the calibration draw and the test point — not a
per-draw high-probability bound; the tests assert exactly that (§8).

---

## 5. Pluggable nonconformity scores

Interface `NonconformityScore` (a `Protocol`); every reference score is a **pure
function of its inputs**:

- **`EnsembleDisagreement`** *(recommended)* — variance across scalar member
  outputs, or mean predictive entropy across member probability vectors, for a
  **decorrelated** ensemble. High disagreement = escalate. This is also the
  day-one mode-collapse guard (§7): a single self-grading model can be
  confidently wrong; a decorrelated ensemble cannot hide its disagreement.
- **`OneMinusMaxSoftmax`** — the classic `1 − max_k p_k`. Cheap, standard,
  weaker (a single overconfident model scores low even when wrong).
- **`DistanceToCalibration`** — Mahalanobis distance of a feature vector to the
  calibration distribution; catches out-of-distribution inputs.

The conformal machinery is agnostic to which score is used — it only requires the
calibration scores to be **exchangeable** with those seen at deployment.

---

## 6. The promote-gate (Execute)

```python
from evolve import promote_if_better, promote_report
promote_if_better(candidate_metrics, baseline_metrics,
                  min_effect=1.0, significance=0.05)   # -> bool
```

Promotes **iff both**:

1. the oriented effect estimate has the **correct sign** (candidate genuinely
   better in the intended direction), **and**
2. the one-sided `(1−significance)` confidence bound on the effect **excludes the
   minimum detectable effect `min_effect`** — not merely excludes zero.

This is deliberately not a single-number compare. It exists because the estate
already shipped a gate that printed *"beats"* for a Δ of **−9.16**: it only
checked that the CI excluded zero, which a solidly-*worse* candidate also
satisfies (its CI sits entirely below zero, on the wrong side). Both guards are
required and both are tested (§8). Default test is a **seeded bootstrap**
percentile CI (distribution-free, reproducible); a numpy-only Welch/one-sample
**t-test** is available with the standard small-`n` caveat.

---

## 7. Knowledge archive and day-one safeguards

**Knowledge (signed, append-only).** Every frozen `q̂` (with `α`, `n_calib`, the
calibration-set hash), every promote verdict (`PromoteReport`), and every
threshold search is appended to the estate's **signed-receipts** log rooted at
the estate **did:web** identity. Append-only + signed = the Knowledge base is
tamper-evident and every past decision is reproducible from its recorded inputs.
*(The receipts/did:web plumbing lives elsewhere in the estate; `evolve` emits the
frozen scalars and provenance for it to sign — it does not re-implement signing.)*

**Day-one safeguards:**

- **Verifier/tracer are READ-ONLY to the optimizer.** The component that scores
  and gates must never be writable by the component being improved, or the loop
  learns to game its own gate. `evolve` holds no optimizer hooks by construction.
- **Frozen, contamination-resistant held-out eval.** The promote-gate compares
  against a *frozen* baseline on a held-out set the optimizer never trains on;
  the calibration set that freezes `q̂` is likewise held out.
- **Shadow → canary rollout.** A promoted candidate first runs in shadow (decisions
  logged, not acted on), then canary (small traffic slice), before full cutover —
  never a hard swap.
- **Decorrelated ensemble to prevent mode collapse.** `EnsembleDisagreement`
  requires genuinely decorrelated members; correlated members hide disagreement
  and let the loop collapse to a single confident-but-wrong mode.

---

## 8. Test guarantees (the point — proven, not asserted)

`pip install -e ".[test]" && pytest` — **70 passed**.

- **Empirical coverage** — synthetic scores from **normal / exponential /
  uniform**, split calib/test thousands of times, across `α ∈ {0.05, 0.1, 0.2}`
  and `n ∈ {50, 200, 500}`: the fraction of test points with `score ≤ q̂` lands
  **inside the sandwich `[1−α, 1−α+1/(n+1)]`** within Monte-Carlo error. Reported
  cells (exponential scores):

  | α | n | target ≥ | empirical | sandwich hi |
  |---|---|---|---|---|
  | 0.05 | 100 | 0.950 | 0.949 | 0.960 |
  | 0.05 | 400 | 0.950 | 0.950 | 0.952 |
  | 0.10 | 100 | 0.900 | 0.900 | 0.910 |
  | 0.10 | 400 | 0.900 | 0.899 | 0.902 |
  | 0.20 | 100 | 0.800 | 0.800 | 0.810 |
  | 0.20 | 400 | 0.800 | 0.800 | 0.802 |

- **Threshold determinism** — same calib multiset + `α` → identical `q̂`
  (order-independent).
- **`+inf` edge** — tiny `n` where `⌈(n+1)(1−α)⌉ > n` returns `+inf`.
- **Tie handling** — heavy ties return the correct order statistic; lower bound
  intact.
- **CRC** — certified bound valid in expectation and tight to `b/(n+1)`; the
  threshold search controls `E[L] ≤ α` on fresh data.
- **`promote_if_better`** — PASS on a genuinely-better candidate; FAIL on a worse
  one; **FAIL on the −9.16 wrong-sign regression**; FAIL within-noise; the
  `min_effect` guard rejects a candidate that clears zero but not `min_effect`.

---

## 9. BUILT vs GAP (honest line)

- **BUILT + tested here:** the router, split-conformal calibration, the coverage
  sandwich, Conformal Risk Control, the pluggable nonconformity scores, and the
  sign-guarded promote-gate — all deterministic, distribution-free, no
  LLM-as-judge, with real empirical-coverage tests (70 passed).
- **[GAP] — owner supplies:** a *live* calibration set drawn from **real estate
  findings** (the actual nonconformity scores the running estate produces), and
  the wiring of the Knowledge emitter into the signed-receipts / did:web log. The
  calibration data must be genuine estate findings — **never arena/benchmark
  data**, whose distribution is not exchangeable with production and would void
  the guarantee.

---

## References

- Vovk, Gammerman, Shafer (2005). *Algorithmic Learning in a Random World.*
  Springer. — split/inductive conformal, exact finite-sample coverage.
- Angelopoulos & Bates (2021). *A Gentle Introduction to Conformal Prediction and
  Distribution-Free Uncertainty Quantification.* arXiv:2107.07511. — the
  `⌈(n+1)(1−α)⌉/n` quantile and the coverage sandwich.
- Angelopoulos, Bates, Fisch, Lei, Schuster (2022). *Conformal Risk Control.*
  arXiv:2208.02814. — bounding `E[L] ≤ α` for monotone losses.
- IBM (2003). *An Architectural Blueprint for Autonomic Computing* — the MAPE-K
  reference loop.
