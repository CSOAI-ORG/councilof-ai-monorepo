#!/usr/bin/env bash
# axis-loop.sh — the AUTOMATED CSOAI axis engine loop.
# Batch-run the GSPC axis measurement on a RunPod GPU pod → pull results → test/audit/check
# → publish/improve → reschedule. Driven by a LaunchAgent (auto) or manually.
#
# Uses: gspc_six_axis_e2e.py (stdlib-only) + the pod's Ollama. Pod must be reachable via the
# SSH alias (see ~/.ssh/config). By default runs the axes whose frozen data is available on the pod.
#
# Usage: ./axis-loop.sh          # one full cycle
set -euo pipefail

POD="${POD:-sov-brain-2}"                       # reachable GPU pod alias
MODELS="${MODELS:-council-oowm:latest}"         # primary model(s)
CONTROL="${CONTROL:-qwen2.5:0.5b-instruct}"     # control arm (base model)
RUN_DIR="/workspace/axis-run"                   # pod working dir
LOCAL_OUT="$HOME/clawd/kimi-regen/evidence/harness/freeze/pod-runs"
LOG="/tmp/axis-loop.log"

# Frozen data on the pod: axis name -> source dir (kaggle-format items.jsonl).
# Map the engine's 6 axes to the frozen dirs on the pod. Add more as data is staged.
declare -A AXIS_SRC=(
  [govbench-eu-ai-act-risk-tier]="gspc_gov_v2_kaggle"    # governance
  [ossbench-licence-vs-use]="gspc_oss_v2"                # openness
  [provbench-article50-survival]="gspc_prv_v2"           # provenance
  # defbench-calibrated-refusal / mcpbench-tool-conformance / pqcbench-postquantum-continuity
  # need their frozen items staged on the pod; add their src dirs here when present.
  )

debug(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; echo "[$(date '+%F %T')] $*"; }

debug "AXIS-LOOP start (pod=$POD)"

# 1. Locate + stage frozen items + engine on the pod, then run each axis.
ssh -o BatchMode=yes "$POD" "mkdir -p $RUN_DIR/benchmark-results/kaggle_benchmarks/hf_datasets $RUN_DIR/evidence/harness/freeze/latest 2>/dev/null; cp /workspace/sovos-repo/gspc_six_axis_e2e.py $RUN_DIR/ 2>/dev/null || true" 2>&1 >> "$LOG"

for axis in "${!AXIS_SRC[@]}"; do
  src="/workspace/.stash/mac-backup/_alignment/${AXIS_SRC[$axis]}/items.jsonl"
  dst="$RUN_DIR/benchmark-results/kaggle_benchmarks/hf_datasets/$axis/items.jsonl"
  if ! ssh -o BatchMode=yes "$POD" "test -f '$src'"; then debug "SKIP $axis — no frozen data at $src"; continue; fi
  # Stage cleaned items (drop canary rows without 'expected').
  ssh -o BatchMode=yes "$POD" "mkdir -p $(dirname "$dst"); python3 -c \"
import json
out=[l for l in open('$src') if l.strip() and 'expected' in json.loads(l)]
open('$dst','w').write('\\n'.join(out)+'\\n')
print(len(out))
\"" 2>&1 >> "$LOG"
  debug "RUN axis=$axis"
  ssh -o BatchMode=yes "$POD" "cd $RUN_DIR && nohup python3 gspc_six_axis_e2e.py --axes '$axis' --models '$MODELS' --control '$CONTROL' --out $RUN_DIR/result-$axis.jsonl > $RUN_DIR/$axis.log 2>&1 & echo started" 2>&1 >> "$LOG"
done

# 2. Wait for the batch to finish (poll for the .jsonl output, then a settle period).
sleep 5
for axis in "${!AXIS_SRC[@]}"; do
  for i in $(seq 1 60); do
    ssh -o BatchMode=yes "$POD" "test -s $RUN_DIR/result-$axis.jsonl && grep -q 'verdict' $RUN_DIR/$axis.log 2>/dev/null && echo done || echo running" 2>/dev/null | grep -q done && break
    sleep 30
  done
done
sleep 15

# 3. Pull results back + TEST/AUDIT/CHECK.
mkdir -p "$LOCAL_OUT"
for axis in "${!AXIS_SRC[@]}"; do
  scp -o BatchMode=yes "$POD:$RUN_DIR/result-$axis.jsonl" "$LOCAL_OUT/" 2>/dev/null && debug "PULLED $axis"
done

echo "=== AXIS-LOOP AUDIT $(date -u +%FT%TZ) ===" >> "$LOG"
for f in "$LOCAL_OUT"/result-*.jsonl; do
  [ -f "$f" ] || continue
  n=$(wc -l < "$f" 2>/dev/null)
  # audit: every row is valid JSON + carries a verdict (honest test)
  bad=$(python3 -c "
import json,sys
b=0
for l in open(sys.argv[1]):
    l=l.strip()
    if not l: continue
    try:
        d=json.loads(l)
        if 'verdict' not in d: b+=1
    except Exception: b+=1
print(b)" "$f" 2>/dev/null || echo '?')
  debug "AUDIT $(basename "$f") — $n rows, $bad missing-verdict"
done

# 4. IMPROVE hook: publish/flag. (Add your promote-gate / corrections-ledger wiring here.)
debug "AXIS-LOOP cycle complete. Results at $LOCAL_OUT"

# 5. RESCHEDULE: the LaunchAgent (StartInterval) re-fires this script. Manual run returns now.
debug "AXIS-LOOP end"
