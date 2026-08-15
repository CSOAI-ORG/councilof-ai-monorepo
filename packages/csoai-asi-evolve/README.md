# csoai-asi-evolve

Sovereign wrapper around [GAIR-NLP/ASI-Evolve](https://github.com/GAIR-NLP/ASI-Evolve) — the AI-researcher loop that proposes, runs, and distils improvements round after round (LEARN → DESIGN → EXPERIMENT → ANALYZE).

## What the sovereign layer adds

- **Ed25519-signed every step** — the *evolution trajectory* is auditable, not just the final candidate. `verify_receipt()` checks any step offline.
- **Care-floor gate** — a candidate is only ACCEPTED if it clears the Maternal-Covenant floor (default 0.85) *and* beats the current best. Evolution cannot tank the estate's own governance floor to chase a benchmark number.
- **Honest scoring** — success comes from a real deterministic predicate you supply; never from a response-length heuristic. A round that produces nothing reports `best=None` rather than a fabricated win.

## Install / test

```bash
pip install -e SOVOS/packages/csoai-asi-evolve
python -m pytest SOVOS/packages/csoai-asi-evolve/tests/ -q   # 9/9
```

## Use

```python
from csoai_asi_evolve import ASIEvolve

loop = ASIEvolve(care_floor=0.85, max_rounds=5, max_candidates_per_round=3)

report = loop.run(
    learn_fn=lambda analysis: researcher_propose(analysis),   # your model
    design_fn=lambda idea: compile_program(idea),
    experiment_fn=lambda program: run_on_predicate(program),  # real eval
    analyze_fn=lambda best: distil_lesson(best),
)
# report["best"] — the winning candidate (measured, signed)
# every step in report["rounds"] carries {kid, sig, payload_sha256} + valid:true
```

## Attribution

- **Upstream:** [GAIR-NLP/ASI-Evolve](https://github.com/GAIR-NLP/ASI-Evolve), Apache-2.0. Wrapper MIT (CSOAI Ltd, UK 16939677). We wrap — we do not fork. Upstream's authors retain their license and credit.
- **Honesty:** this is a *harness*, not a claim of achieved ASI. It runs the loop; whether it reaches your target is a measured result in the signed report.
