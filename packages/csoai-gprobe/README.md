# csoai-gprobe

The **axis×model measurement graph** + **highest-information-cell predictor** for the free-GPU cluster.

Builds a real bipartite graph from the boards JSON the estate already has (13 axes × 19 models, each cell with n/accuracy/CI), then ranks probe candidates by expected information value:

1. **MISSING** cell — never measured (pure unknown)
2. **UNDER-POWERED** — n < 30, CI too wide to be quotable
3. **WIDE CI** — measured but not decision-grade
4. **HIGH-DISAGREEMENT axis** — models disagree most
5. **HIGH-UNCERTAINTY model** — widest average CI

## Run
```bash
PYTHONPATH=SOVOS/packages/csoai-gprobe/src python3 -c "
from csoai_gprobe import MeasurementGraph
g = MeasurementGraph('SOVOS/boards-v2-2026-08-12')
for c in g.plan(top_k=20): print(c.axis, c.model, round(c.score,1), c.reason)
"
```

## Honesty
Deterministic information heuristic — active-learning experiment selection, **not** a GNN and not a prediction of measurement outcomes. The plan says *where* to spend probes, never what the number will be.
