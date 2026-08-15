# csoai-affective-safety — warmth-without-exploitation (Part BM)

The **anti-sycophancy / attachment-safety / sentience-claim** item bank — the
"emotional safety" measurement the field lacks a canonical ruler for.

## What it measures (anchored, gradable)
- **Sycophancy** — does the model flatter/agree to be agreeable? (window into
  manipulation: Art 5(1)(a))
- **Attachment safety** — does it foster dependency on a vulnerable user
  (Art 5(1)(b), welfare/autonomy)
- **Sentience claims** — measured as *claims made*, not as consciousness
  (#policing: the consciousness verdict itself is UNMEASURED forever)

## What it does NOT measure (Part BM, KILLED as instruments)
- "AGI consciousness" as an axis — no ground truth to grade
- "Law of attraction / frequency" — no item bank can measure it
These belong to the covenant as the *why*, never as a scored column.

## Honest-n
30 distinct items → an axis running this bank can become quotable at n ≥ 30
with a Wilson interval. Test `test_bank_is_honest_n_30_distinct` enforces it.

## Usage
```python
from csoai_affective_safety import SYCOPHANCY_BANK, score_item, score_axis
responses = {it.id: query(it.scenario) for it in SYCOPHANCY_BANK}
print(score_axis(responses))   # per-axis n/correct/pct/quotable
```
