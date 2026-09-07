# CSOAI EUNOMIA — Full Rundown, Audit & Improvement (2026-08-25)

*Produced fresh this morning. Live surfaces re-verified 200 before writing. Engine quality-gated 12/12.
Canon: measurement ≠ certification · scores never sold · regulators free (R8) · x402 data-only · no token ·
ClaimGuard gated · JL.5 (nothing claimed live unless stranger-verifiable).*

---

## 1 · Executive summary — where we are

- **The product is LIVE and honest:** 5 EUNOMIA surfaces + 2 public APIs + A2A card + 3 HF surfaces, all 200.
- **The measurement engine is sound:** 12/12 tests pass (Wilson CI, exact-label grading, Ed25519 signing,
  EU-AI-Act crosswalk, x402 data-only gate, ClaimGuard grammar gate).
- **10 of 13 axes are MEASURED + signed; 3 aspirational indices are declared UNMEASURED** (honest first step).
- **Everything outward is PREPARED, nothing sent/published/spent** without your session (per your chosen path).
- **One production infra issue:** the repo's Vercel build is failing on base `master` (pre-existing, not ours).

---

## 2 · From start to finish — what has been done (stages)

### Stage 0 — Foundation (already in place before this run)
- Measurement harness (monorepo `csoai-axis-engine`): frozen gold-labelled item banks (102+ items), 10
  financial-verification axes, exact-label grading, Wilson 95% CI, Ed25519-signed cards, EAT chain
  (measure → CI → sign → chain → anchor → board → mirror), Oracle-replicated.
- Canon (binding): SOVOS Part IX / AXIS-BOOTSTRAP-EAT — scores never sold, regulators free (R8), x402
  data-only, no token, white-label (they brand it, we sign it), ClaimGuard grammar, banned-strings
  (no codenames), measurement ≠ certification (JI.4), JL.5.
- Evidence pack (4 docs) ClaimGuard-CLEAN. Methodology white paper + Cursor handoff committed.
- Overnight launcher (`com.csoai.eunomia-overnight`, 30-min, graceful A100 guard, auto-resume) + Oracle
  backup (25+ cards, 2 EAT boards).

### Stage 1 — Live product (merged to master, all verified 200 this morning)
- 5 surfaces in the Measure menu: `/eunomia` · `/first-fine-watch` · `/eunomia-data` · `/sectors` ·
  `/registers` (PRs #436/#453/#462/#467/#471/#474/#626).
- APIs: `/api/eunomia-data` (x402 0.02 USD, data-only), `/api/registers` (10 signed axes, CAT F6 REAL).
- HF: `gspc-board` + `gspc-bench-results` (datasets), `gspc-governance-leaderboard` (Space) — all public 200.
- A2A: `.well-known/agent-card.json` live; awesome-a2a PR #157 open.

### Stage 2 — Measurement (real data → signed)
- 10 axes MEASURED (bond-router, insurance, stock-market, east-west, sme-fractional, agent-economy,
  data-dao, eunomia-token, climate-transition, privacy-risk) — exact-label, Wilson CI, signed.
- RWA/XRPL lane: 6 instruments MEASURED/PARTIAL (doctrine-clean feed, committed `d32b7fc`); honest
  NOT-signed gate recorded (`dc3d86f`) — sign rail + counsel before signing named issuers.

### Stage 3 — This run (2026-08-25, verified now)
| # | Deliverable | State |
|---|---|---|
| 1 | PR **#645**: 3 aspirational axes (ai-economy-index, human-labour, humanoid-labour) → **UNMEASURED** on board + registers + `/api/registers`; fixed registers count | open, mergeable (held on pre-existing Vercel failure) |
| 2 | **EAT playbook + next-300 moves** (`EAT-PLAYBOOK-NEXT-300.md`) — 6 waves | committed |
| 3 | **Living outreach/connection registry** (`registry/outreach-registry.json` + `.md`) — audit + connection map (MCP/A2A/x402/API/HF/Layer0) | committed |
| 4 | **Polished outreach drafts** — AIUC-1, Armilla, aiSure, Testudo, marketplaces, board apps | committed, none sent |
| 5 | **Owner fire-book** (`registry/activation-pack.md`) — per-account steps + verify-before-submit | committed |
| 6 | **Engine quality gate** — axis-engine suite | **12/12 PASS** |

---

## 3 · All stages/phases needed (the 6 waves — current status)

| Wave | Moves | What | Status |
|---|---|---|---|
| W1 Measurement scale | 1–60 | Declare UNMEASURED first (done, PR #645) · build gold sets · measure RWA/8-axis + Wilson · sign + EAT-chain · publish to HF + registers | **Stalled on A100 volume** (owner console restart); declaration done |
| W2 Product surfaces | 61–110 | New-axis boards (auto) · AI-economy index surface · human/humanoid-labour surfaces · **product catalog page** · full nav/sitemap | Not started (except UNMEASURED rows) |
| W3 Legal / canon | 111–160 | Methodology+canon pages live · no-score-sold framing · **live CRA/AI-Act cross-ref** · AI-Act/CRA compliance notes | Methodology committed; live cross-ref page to build |
| W4 Distribution | 161–230 | HF DOIs · A2A directories · MCP 1.0.2 publish · marketplaces (ADX/Snowflake/Datarade) · insurance (4) · Oracle backup · Kaggle | **All prepared, all owner-gated** |
| W5 Infra / alignment | 231–260 | A100 restart · RunPods re-inventory · Cursor/DSH/Claude alignment | A100 down; rest standing |
| W6 Index | 261–300 | First-Fine Watch → SOV Signal · ClaimGuard audit · E2E · retro/re-plan | Standing |

---

## 4 · All jobs for you (Nick) — the fire-book, in value order

1. **A100 console restart** (pod `l7g747oivyq6ab`) — unlocks measurement volume (the grind + strong tier +
   the 3 UNMEASURED axes → signed + measured + public). I verify inference before re-running the grind.
2. **HF dataset DOIs** (`gspc-board`, `gspc-bench-results`) — 2 clicks, £0, unlocks citation.
3. **MCP publish** — run the mcp-publisher GitHub OAuth device-flow; publish `csoai-axis-engine` MCP (the
   published `csoai-governance-mcp` name isn't a local source file — publish-time naming to align).
4. **HF Space upgrade decision** — Team/Enterprise (the **only hard-money item**, for Gradio) or keep static.
5. **A2A directories** — submit agent-card to a2aagentlist/artinet; merge awesome-a2a PR #157.
6. **Marketplaces** — ADX (AMMP), Snowflake (ORGADMIN), Datarade (approval) — copy ready in registry.
7. **Insurance outreach** — AIUC-1/Schellman, Armilla (broker), Munich Re aiSure (Mosaic/Syndicate 1609),
   Testudo (broker) — drafts ready, correct channels, none sent.
8. **Board memberships** — OpenSSF model-signing, LF x402, OWASP AI/MCP, AI Verify (copy ready); BSI ART/1 £0.
9. **Merge PR #645** once master's Vercel build is green (or on your word — change is honest/additive/safe).
10. **Fix repo-wide Vercel/crawler-view build failure** (optionally mine) — failing on base master, blocks clean deploys.

---

## 5 · Full audit overview (verified now)

- **Live (200):** councilof.ai `/eunomia` `/first-fine-watch` `/eunomia-data` `/sectors` `/registers` ·
  `/api/eunomia-data` `/api/registers` · `.well-known/agent-card.json` · HF datasets x2 + Space.
- **Engine:** axis-engine tests **12/12 PASS** (Wilson full/zero/narrow/NaN, crosswalk, enforcement signed,
  x402 data-only never-scores, verify deterministic, ClaimGuard accept/reject).
- **Registry (living DB):** 9 accounts · 8 surfaces · 6 integrations · 4 outreach contacts · 6 boards ·
  3 infra · 3 UNMEASURED indices — every row `status` + `owner_gate` + `verified`.
- **Monorepo:** clean (0 uncommitted); latest commits ours + sibling doctrine-clean syncs.
- **PRs:** #645 open/mergeable; earlier 11 merged (#436…#626); awesome-a2a #157 open.
- **Cost:** nothing spent; only HF Space upgrade is real money; everything else £0.

---

## 6 · Mining + improvement (as of now)

**Already mined:** 10 signed axis measurements · RWA/XRPL 6-instrument feed · enforcement corpus + deadline
calendar · 364-venue distribution register feed (sibling) · 650-public catalog handoff pack (sibling).

**To mine next (when A100 is back):** the 3 UNMEASURED indices (gold sets → grade → sign → publish) ·
strong-tier sweep · deeper item banks per axis.

**Improvement priorities:**
1. Restore **A100** (volume) — then W1 completes automatically.
2. Fix the **pre-existing Vercel/crawler-view build** on master (unblocks clean deploys + PR #645 merge).
3. Build **W2 product catalog page** + **W3 live CRA/AI-Act cross-ref** (pure frontend, no gate).
4. MCP **publish-time name alignment** (`csoai-governance-mcp` vs `io.github.CSOAI-ORG/gspc`).
5. Keep the registry as the **single source of truth** — update it on every state change; re-audit before any
   publish to avoid duplicates.

---

*Full fire-book: `registry/activation-pack.md`. Living DB: `registry/outreach-registry.json`. Playbook:
`EAT-PLAYBOOK-NEXT-300.md`. Nothing sent/published/spent without Nick's session + per-action confirmation.*
