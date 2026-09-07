# CSOAI ALIGNMENT — paste this block to Grok Bot (or any agent: DSH, Cursor, Claude)

**2026-08-28 · authoritative, verified. Single source of truth: monorepo `registry/`.**

════════════════════════════════════════════════════════════════════════

## 1 · FLEET (ports MOVE on pod restart — re-resolve via API, never assume dead)
| Pod | SSH | GPU | Role |
|---|---|---|---|
| sov-repull-20260808 | `-p 12473 root@194.26.196.156` | RTX3090 | BUILD BOX — `/workspace/councilof-ai`, node22, deps; site builds run here |
| sovos-light-master-mine | `-p 13440 root@38.128.232.57` | A100-class $1.39/hr | MEASUREMENT ENGINE — ollama fleet (14), axis-engine.sh + arena-auto-loop.sh RUNNING; GPU shows 0% BETWEEN batches (it lies) |
| oowm-agent-01-hub | `-p 39331 root@38.80.152.147` | cpu | OOWM hub |
| oowm-agent-03-mine | `-p 53390 root@213.173.105.92` | cpu | OOWM miner |
| oowm-agent-04-route | `-p 33035 root@213.173.105.102` | cpu | OOWM router |
| oowm-agent-05-product | `-p 41054 root@103.196.86.88` | cpu | OOWM product |
| sov-volume-sink-cpu | `-p 55664 root@213.173.105.83` | cpu | durability sink — ONLY pod with network volume `sovos-merge-800` (800GB EU-RO-1) |

Re-resolve ports: `K=$(grep -oE '[a-zA-Z0-9_-]{20,}' ~/.runpod/config.toml | head -1)` then RunPod GraphQL
`query{myself{pods{name runtime{ports{ip publicPort}}}}}`. Key: `~/.runpod/ssh/runpodctl-ssh-key`.
Volumes: sovos-merge-800 (EU-RO-1) · k3-weights-2tb · sov-models/sov-artifacts/sov-workspace (region-locked).
Durability: sink cron `:17 */2h` runs `/workspace/durability-sync.sh` → `/workspace/durability/{3090-build,a100-measure}`.

## 2 · DOCTRINE (decisions — do not "fix")
- Owner rulings: `public/signed/card_index.json` = EXACTLY 150 rows (313 files INTENDED) · `chain.json` DELETED
  deliberately · `signed-json-guard.mjs` enforces both.
- Content: never "certification" · no public prices · **never type a count — derive from GET /api/gspc or
  /api/state (board = 22 axes · 15 measured · 7 unmeasured)** · "unmeasured" is first-class · new routes MUST be
  in `PRIMARY_PATHS` (library-ia.ts) or they ship "archived".
- Git: master ONLY integration branch · NO new worktrees · batch pushes (don't starve GHA) · stage by name ·
  never `git add -A` in main checkout · root `src/` DEAD.
- Signups: drive an ALREADY-authenticated session + stage to submission ONLY. Never create accounts/enter
  passwords/accept ToS/send email without Nick's explicit go per item.
- Verify cards: `curl -s https://councilof.ai/signed/verify-card.mjs -o v.mjs && node v.mjs card.json`
  → VALID / INVALID(reason) / UNCHECKABLE (three states, never two).

## 3 · LIVE PRODUCT STATE (EUNOMIA — verified 200, 2026-08-28)
- Surfaces: `/eunomia` `/registers` `/first-fine-watch` `/eunomia-data` `/sectors` + `/eunomia-catalog` +
  `/eunomia-crosswalk` (all in Measure menu).
- APIs: `/api/registers` = **13 axes (10 MEASURED + 3 UNMEASURED: ai-economy-index, human-labour,
  humanoid-labour)** · `/api/eunomia-data` (x402 0.02 USD data-only, never scores).
- HF: `csoai/gspc-board` + `gspc-bench-results` (DOIs 10.57967/hf/10114+10116) + Space — ⚠️ HF mirrors are a
  STALE 14-axis subset vs live 22-axis board (board lane to re-mirror; signed board.json untouched).
- A2A: `.well-known/agent-card.json` live. Registry: `registry/outreach-registry.json` = the living DB
  (accounts · surfaces · integrations · contacts · boards · infra · fleet · doctrine).

## 4 · IN FLIGHT / NEXT
- MCP publish (mcpName fix ready: `io.github.CSOAI-ORG/gspc`; needs Nick's device-flow) · a2aagentlist email
  ready · awesome-a2a re-target to ai-boost · Datarade/AWS/Snowflake staged · boards £0 path ready.
- Measurement engine RUNNING on A100 — grind + arena producing (47 signed cards on pod).
- Free-tier programmes to stage for Nick: NLnet NGI Zero (opens 3 Sep) · AIRR Rapid Access (20k GPU hrs) ·
  NVIDIA Inception · HF org credits.

## 5 · KNOWN ISSUES (flag, don't fix silently)
1. **Durability sync FAILING on sink** (log `3090-build FAIL` + `a100-measure FAIL` since 06:44; dry-run rsync
   code 255 broken-pipe) — pod-local work at risk on terminate. Infra lane to fix (likely sink SSH key/auth).
2. csoai.org content drift (Council OS · Measurement 4,543b) + www.csoai.org SSL broken (ticks 334-342) — CF
   dashboard/Nick.
3. HF mirror divergence (14 vs 22) — board lane re-mirror.
4. arXiv G6Y9SY HARD deadline passed (27 Aug 04:00) — Nick to reconcile.

════════════════════════════════════════════════════════════════════════
_Measurement ≠ certification. Scores never sold. x402 data-only. No token. £0 spend this cycle._
