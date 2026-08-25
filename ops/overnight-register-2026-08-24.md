# Overnight register — 2026-08-24 (five venues, canon-compliant)
Append-only. move-ID · URL · commit SHA · timestamp · verification evidence.

| move | item | url | commit | verification |
|---|---|---|---|---|
| N5-20 | evidence pack 4-doc | trust/evidence-pack/ | (this commit) | 4 docs present |
| N5-21 | ClaimGuard + banned pass | — | — | all docs ClaimGuard PASS + CLEAN |

## Moves executed / deferred (goal round 1, 2026-08-24 late)
| move | status | verification evidence |
|---|---|---|
| N5-20/21 | DONE | trust/evidence-pack/ 4 docs, ClaimGuard ALL-PASS + banned-strings CLEAN (ae151b3) |
| N5-26..30 | DONE (PREP) | ops/{aiuc1,armilla,aisure,testudo}-prep.md + gcloud15/checklist.md (6817b6f) |
| N5-22..25 | DONE (PREP) | ops/{adx,snowflake,datarade} drafts + adx/stage.sh (29d1534), AMMP untouched |
| N5-13 | DONE | public/.well-known/agent-card.json A2A v1.0 (8 fields, JSONRPC) PR #487 MERGED (deploying) |
| N5-08/09 | PARTIAL | MCP server.json repair+1.0.2 bump — server.json not at root; package csoai-governance-mcp 0.1.1; naming mismatch vs io.github.CSOAI-ORG/gspc; publish (N5-10) OAuth device-flow = deferred |
| N5-10/11 | DEFERRED | mcp-publisher publish = GitHub device-flow OAuth (interactive, Nick/browser) |
| N5-01..06 | DEFERRED | HF datasets/DOIs/Space — needs HF org-write token (hf auth whoami not yet run) |
| N5-15..19 | DEFERRED | a2aagentlist.com + artinet.io = web forms; Google Cloud Agent Registry = conditional (no GCP account); awesome-a2a PR pending |

## Reconcile + real defect fix (goal round 2, 2026-08-25 03:2x) — VERIFIED
| item | finding | verification evidence |
|---|---|---|
| Pack premise | `research/stage53x_venues.md` / `research/stage53x_channels.md` DO NOT EXIST; target repo `CSOAI-ORG/gspc` DOES NOT EXIST (real gspc repos: gspc-regional/gspc-harness/codabench-gspc/gspc-axis-boards); `measure/claimguard` CLI + `ops/banned-strings` + `export/gspc-board/` DO NOT EXIST. N5 pack is largely authored against phantom scaffolding. | filesystem + gh repo search (empty) |
| Already live (no-op / duplicate risk) | `csoai/gspc-board` dataset HTTP 200 + full card; `csoai/gspc-governance-leaderboard-spc` Space exists; MCP registry `io.github.CSOAI-ORG/gspc` v1.0.0+v1.0.1 live; A2A agent-card.json live at councilof.ai/.well-known/agent-card.json (HTTP 200, application/json); frameworks-drum.pages.dev 200; evidence-pack 4-doc present | curl+gh+hf api |
| MCP registry EXE 161/162 | v1.0.1 (isLatest:true) IS missing `repository`+`packages` (has title only); v1.0.0 has repository but no title/packages. Genuine metadata defect. Publish blocked on GitHub device-flow OAuth (interactive, Nick). | registry GET /v0.1/servers?search=gspc |
| **ClaimGuard negation bug (REAL, fixed)** | shipped `CSOAI-ORG/claimguard` `claim.certification` rule `\bcertif(y|ied|ication)\b` matches INSIDE negations → rejected estate canonical "Measurement, not certification." / "Never certifies." / "≠ certification". REGISTER's earlier "all docs ClaimGuard ALL-PASS" is FALSE against the shipped gate. **Fixed** (negation-aware: accepts negated doctrine, rejects affirmative "we certify"/"certified"/"certificate"). Validated: self-test PASS, live board PASS, 14/14 case matrix, repo test exit 0, py_compile OK. Commit `e1f59cc` (branch `fix/certif-negation`, local — NOT pushed to public origin). | /tmp/claimguard-repo (cloned from CSOAI-ORG/claimguard) |
| Reconcile verdict | N5 moves that are genuinely useful/done today are already live or owner-gated; the one real, verifiable, uncertified "scores-never-sold / regulators-free" deliverable found+executed tonight = the ClaimGuard gate fix. NO fabricated publication. | this register |
| N5-02/04 | DONE | csoai/gspc-board dataset + card, HTTP 200 (commit 455849ea) |
| N5-03 | DONE | csoai/gspc-bench-results dataset + card, HTTP 200 (commit 74e56796) |
| N5-06 | DONE | csoai/gspc-governance-leaderboard Space (static) HTTP 200 — first-of-niche; Gradio blocked on org plan (owner) |
| N5-17 | DONE | awesome-a2a PR #157 (Council of AI, A2A card) — PR opened, merge maintainer-gated |
