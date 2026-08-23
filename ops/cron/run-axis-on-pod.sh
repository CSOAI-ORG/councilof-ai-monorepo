#!/usr/bin/env bash
# run-axis-on-pod.sh — stage + run the CSOAI axis engine (gspc_six_axis_e2e.py) on a RunPod GPU pod.
# Fixes "no work on the pods": the axis engine lives on the Mac; this pushes it + the frozen
# item files to the pod's /workspace and runs a GSPC six-axis measurement there.
#
# PREREQ: pod SSH alias configured in ~/.ssh/config (e.g. sovos-light-a100) with the runpod key.
#
# Usage:  ./run-axis-on-pod.sh [POD_ALIAS] [MODEL] [CONTROL]
#   default POD_ALIAS=sovos-light-a100, MODEL=council-oowm-hardened, CONTROL=llama3.2:3b
set -euo pipefail

POD="${1:-sovos-light-a100}"
MODEL="${2:-council-oowm-hardened}"
CONTROL="${3:-llama3.2:3b}"
SRC="$HOME/clawd/kimi-regen"
ENGINE="$SRC/gspc_six_axis_e2e.py"

# 1. Locate the frozen item files (the engine reads benchmark-results/kaggle_benchmarks/hf_datasets/<axis>/items.jsonl).
echo "== locating frozen axis items =="
FROZEN=""
for cand in \
  "$SRC/benchmark-results/kaggle_benchmarks/hf_datasets" \
  "$HOME/clawd/csoai-static-deploy2/benchmark-results/kaggle_benchmarks/hf_datasets" \
  "$HOME/projects/coai-dashboard/benchmark-results/kaggle_benchmarks/hf_datasets"; do
  [[ -d "$cand" ]] && { FROZEN="$cand"; break; }
done
if [[ -z "$FROZEN" ]]; then
  echo "FATAL: frozen items not found under kimi-regen / csoai-static-deploy2 / coai-dashboard."
  echo "Find the dir holding govbench-eu-ai-act-risk-tier/items.jsonl and set FROZEN."
  exit 1
fi
echo "   frozen: $FROZEN"

# 2. Push engine + frozen data + fleet-census to the pod /workspace.
echo "== pushing engine + frozen data to $POD:/workspace/axis-engine =="
ssh -o BatchMode=yes "$POD" "mkdir -p /workspace/axis-engine" 2>&1
scp -o BatchMode=yes "$ENGINE" "$POD:/workspace/axis-engine/" 2>&1 | tail -1
tar -C "$(dirname "$FROZEN")" -czf - "$(basename "$FROZEN")" 2>/dev/null \
  | ssh -o BatchMode=yes "$POD" "tar --no-same-owner -xzf - -C /workspace/axis-engine" 2>&1 | tail -2
scp -o BatchMode=yes "$SRC/evidence/harness/freeze/latest/fleet-census.json" "$POD:/workspace/axis-engine/" 2>&1 | tail -1

# 3. Run the axis engine on the pod (Ollama is on the pod's localhost:11434).
echo "== running GSPC six-axis E2E on $POD (model=$MODEL control=$CONTROL) =="
ssh -o BatchMode=yes "$POD" \
  "cd /workspace/axis-engine && GOVBENCH_OLLAMA_URL=http://localhost:11434 \
   python3 gspc_six_axis_e2e.py --models '$MODEL' --control '$CONTROL' \
   --out /workspace/axis-engine/gspc-six-axis-e2e.jsonl 2>&1 | tail -40" 2>&1 | tail -40

# 4. Pull the results back.
echo "== pulling results =="
mkdir -p "$SRC/evidence/harness/freeze/pod-runs"
scp -o BatchMode=yes "$POD:/workspace/axis-engine/gspc-six-axis-e2e.jsonl" "$SRC/evidence/harness/freeze/pod-runs/" 2>&1 | tail -1
echo "DONE. Results: $SRC/evidence/harness/freeze/pod-runs/gspc-six-axis-e2e.jsonl"
