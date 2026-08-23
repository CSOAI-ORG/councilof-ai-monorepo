# csoai-axis-engine

The automated CSOAI GSPC **axis measurement engine**: frozen item sets → live LLM generation on
a RunPod GPU → exact-label grading → Wilson CI → control-arm comparison → signed evidence record.

## Pipeline
`frozen items.jsonl` → `/api/chat` (Ollama on the pod) → exact-label grade → per-label counts
→ Wilson CI → result JSON (honest `signed:false` until the #dsh rail ships).

## Files
- `src/csoai_axis_engine/gspc_six_axis_e2e.py` — the 6-axis E2E engine (governance/safety/provenance/conformance/openness/continuity).
- `src/csoai_axis_engine/axis_measure.py` — the curl-based single-axis runner (bypasses a urllib→Ollama hang).

## Automation (ops/cron)
- `axis-loop.sh` — batch-run → pull → test/audit → improve → reschedule (LaunchAgent `com.csoai.axis-loop`, every 30 min).
- `run-axis-on-pod.sh` — stage + run the engine on a GPU pod.

## Frozen data
Per-axis `items.jsonl` staged on the pod at
`/workspace/axis-run/benchmark-results/kaggle_benchmarks/hf_datasets/<axis>/items.jsonl`
(e.g. `govbench-eu-ai-act-risk-tier`). Overlive sources in `csoai-static-deploy2` / `kimi-regen`.

## Honesty
- `UNMEASURED` stays `UNMEASURED`. Control-arm is mandatory (the engine refuses to run without it).
- Exact-label grading measures emitted labels, not comprehension (documented in the engine).
- `signed:false` until the #dsh Ed25519 rail ships (the true-measurement-body gap).
