#!/usr/bin/env bash
# backup-eat-to-oracle.sh — EAT box 7 (mirror): back up the signed axis cards +
# eat-board + eat-mirror from the A100 measurement pod to the Oracle Free Tier
# micros. Runs on any node holding both the A100 key and the Oracle key.
# Idempotent; logs a dated receipt. Rerun as cron for a continuous back-up path.
set -uo pipefail

A100_HOST=root@38.128.232.57
A100_PORT=23166
A100_KEY=~/.runpod/ssh/runpodctl-ssh-key
A100_SRC=/workspace/axis-engine
ORACLE_USER=ubuntu
ORACLE_HOSTS=(141.147.73.85 145.241.232.16)   # micro-2, micro
ORACLE_KEY=~/.ssh/id_ed25519
ORACLE_DEST=/home/ubuntu/csoai-eat-backup
STAGE=${STAGE:-/tmp/csoai-eat-stage}
LOG=${LOG:-$HOME/csoai-eat-backup.log}

STAMP=$(date -u +%Y%m%d-%H%M%S)
TAR=eat-evidence-${STAMP}.tgz
mkdir -p "$STAGE"

echo "[$(date -u +%FT%TZ)] backup start $TAR" >> "$LOG"

# 1. tar the EAT evidence on the A100.
ssh -i "$A100_KEY" -o StrictHostKeyChecking=no -p "$A100_PORT" "$A100_HOST" \
  "cd $A100_SRC && tar czf /tmp/$TAR card-*.signed.json eat-board.json eat-mirror 2>/dev/null && echo ok" \
  | grep -q ok && echo "[$(date -u +%FT%TZ)] tarballed on A100" >> "$LOG" \
  || { echo "[$(date -u +%FT%TZ)] A100 tar FAILED" >> "$LOG"; exit 1; }

# 2. pull to local stage.
scp -i "$A100_KEY" -o StrictHostKeyChecking=no -P "$A100_PORT" "$A100_HOST:/tmp/$TAR" "$STAGE/" \
  >>"$LOG" 2>&1 && echo "[$(date -u +%FT%TZ)] pulled to stage" >> "$LOG"

# 3. push to each Oracle micro + extract.
for H in "${ORACLE_HOSTS[@]}"; do
  echo "[$(date -u +%FT%TZ)] pushing to $H" >> "$LOG"
  ssh -i "$ORACLE_KEY" -o StrictHostKeyChecking=no "$ORACLE_USER@$H" "mkdir -p $ORACLE_DEST" 2>>"$LOG"
  scp -i "$ORACLE_KEY" -o StrictHostKeyChecking=no "$STAGE/$TAR" "$ORACLE_USER@$H:/tmp/" >>"$LOG" 2>&1 \
    && ssh -i "$ORACLE_KEY" -o StrictHostKeyChecking=no "$ORACLE_USER@$H" \
       "tar xzf /tmp/$TAR -C $ORACLE_DEST 2>/dev/null; rm -f /tmp/$TAR" >>"$LOG" 2>&1 \
    && echo "[$(date -u +%FT%TZ)] backed up to $H OK" >> "$LOG" \
    || echo "[$(date -u +%FT%TZ)] backup to $H FAILED" >> "$LOG"
done
rm -f "$STAGE/$TAR"
echo "[$(date -u +%FT%TZ)] backup complete $TAR" >> "$LOG"
echo "see $LOG"
