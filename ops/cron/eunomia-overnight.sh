#!/usr/bin/env bash
# eunomia-overnight.sh — autonomous overnight EUNOMIA pipeline.
# Runs from the Mac (holds both the A100 key and the Oracle key). Each cycle:
#   1) ensure the A100 EUNOMIA measurement grind is running (0.5b tier, reliable);
#   2) collect any new axis result JSONs;  sign + EAT-chain;
#   3) Oracle-back-up the signed evidence + chain.
# Logs a dated receipt. Idempotent, cron/launchd-ready.
set -uo pipefail

A100=root@38.128.232.57
A100_PORT=23166
A100_KEY=~/.runpod/ssh/runpodctl-ssh-key
A100_DIR=/workspace/axis-engine
LOG=${LOG:-$HOME/eunomia-overnight.log}
STAMP=$(date -u +%Y%m%d-%H%M%S)

echo "[$(date -u +%FT%TZ)] overnight cycle $STAMP start" >> "$LOG"

# 1) Ensure the 0.5b EUNOMIA axis grind is running on the A100 (reliable tire).
ssh -i "$A100_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$A100_PORT" "$A100" '
  cd /workspace/axis-engine 2>/dev/null || exit 0
  # start governance grind if absent (already-running grind keeps signing cards)
  if ! ps -eo args | grep -q "[b]ash governance-grind.sh"; then
    setsid bash governance-grind.sh >> governance-grind.log 2>&1 < /dev/null &
  fi
' >>"$LOG" 2>&1

# 2) Collect + sign + EAT-chain any un-chained fresh axis results (0.5b tier card-*.signed.json).
ssh -i "$A100_KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 -p "$A100_PORT" "$A100" "
  cd $A100_DIR
  # sign any result-*.json (0.5b) that lacks a card-*.signed.json
  for f in result-*.json eunomia-*-result.json; do
    [ -f \"\$f\" ] || continue
    ax=\$(basename \"\$f\" .json | sed -E 's/^(result-|eunomia-)//')
    [ -f \"card-\$ax.signed.json\" ] || python3 sign_result.py \"\$f\" sigil_ed25519.key \"card-\$ax.signed.json\" 2>/dev/null
  done
  python3 eat_chain.py --dir . --glob 'card-*.signed.json' --key sigil_ed25519.key --board eat-board.json --mirror eat-mirror 2>/dev/null | head -2
" >>"$LOG" 2>&1

# 3) Oracle-back-up the signed evidence + chain (both micros).
bash "$(dirname "$0")/backup-eat-to-oracle.sh" >>"$LOG" 2>&1

echo "[$(date -u +%FT%TZ)] overnight cycle complete" >> "$LOG"
echo "cycle complete — see $LOG"
