# CSOAI Owner Fire-Book — activation & sends (fire-ready)

**How this works (per your direction):** Nick opens an authenticated browser session for each account below.
I prepare the exact step + content + what I'll verify after; Nick submits. **No plaintext password used; no bulk
blast; no duplicate send.** Re-audit `registry/outreach-registry.json` before any step.

Every step is ordered so nothing re-builds an already-live surface. All verified URLs below are current (2026-08-25).

---

## 1 · Hugging Face (owner web-UI) — the ONE cost item
- [ ] **Dataset DOIs** for `csoai/gspc-board` + `csoai/gspc-bench-results` — in dataset settings → "Create DOI".
  *Cost: £0, but a web-UI action that locks rename/visibility.*
- [ ] **Space `gspc-governance-leaderboard`**: current org plan blocks Gradio. If we need the interactive app
  live, upgrade to **Team/Enterprise** (this is the only hard cost I can see). Else it stays a static Space.
- [ ] After: **I verify** both datasets still 200 + the Space 200. Confirm no duplicate Space/dataset.

## 2 · MCP Registry publish (owner OAuth)
- [ ] Fix the name mismatch in-repo: package `csoai-governance-mcp` **0.1.1** vs registry name
  `io.github.CSOAI-ORG/gspc`. Align package.json `name` to the registry name, bump to **1.0.2**.
- [ ] Nick runs the **mcp-publisher GitHub OAuth device-flow** (paste the one-time device code in your browser).
- [ ] Publish `csoai-governance-mcp@1.0.2`.
- [ ] **I verify** the registry page returns the tool set + 0.4xx.

## 3 · A2A directories + agent-card
- [ ] `agent-card.json` already live (200). Submit to **a2aagentlist** + **artinet** web-forms (owner).
- [ ] **awesome-a2a PR #157** is open — Nick merges (or re-confirms the PR is clean).
- [ ] **I verify** agent-card.json 200 + directory listings resolve.

## 4 · Marketplaces (owner / ORGADMIN / approval)
- [ ] **AWS Data Exchange (AMMP)** — initiate AMMP listing of the signed data asset.
- [ ] **Snowflake Marketplace** — needs **ORGADMIN**; publish the data product.
- [ ] **Datarade** — complete approval + upload the data-room pack (signed record + deadline calendar).
- [ ] **I verify** each listing/screenshot AFTER publish; record in registry as LIVE + verified URL.

## 5 · Outreach sends (the 4 drafts — submit via the correct channel)
- [ ] **AIUC-1 / Schellman** — formal scoping + SoA. Use `outreach-drafts/aiuc1.md`. Submit via their portal/
      scheme process, not cold email. ≥ feedback in weeks; fees not public.
- [ ] **Armilla** — broker-distributed, hello@armilla.ai. Use `outreach-drafts/armilla.md`. ≥90-day prep.
- [ ] **Munich Re aiSure** — via Mosaic / Lloyd's Syndicate 1609 (broker). Use `outreach-drafts/aisure.md`.
- [ ] **Testudo** — broker. Use `outreach-drafts/testudo.md` (one-pager; no code access needed).
- [ ] **I verify** nothing was sent twice (registry `sent:false` for each before send), and mark `sent:true`
      after each — the living DB is the anti-duplicate guard.

## 6 · Board memberships (applications)
- OpenSSF model-signing · LF x402 Foundation · OWASP AI/MCP · AI Verify Foundation.
- [ ] Nick submits each application (or I prepare it in-browser for submission).
- [ ] Firewall: never lobby for certification powers, never pre-brief a vendor client, never a seat that
      conflicts with measurement neutrality.
- [ ] **BSI ART/1** — UK mirror of ISO/IEC SC 42, £0. Pack at `SOVOS/BSI_ART1_SEAT_2026-08-15.md` (gated).

## 7 · A100 restart (measurement volume) — owner console
- [ ] RunPod console restart of pod `l7g747oivyq6ab` (`sovos-light-master-mine-20260816`).
- [ ] **I verify** inference is healthy before re-running the grind (SSH + `ollama list` works ≠ inference works).

## 8 · After each step (universal)
- Re-audit `registry/outreach-registry.json`; update `status`/`verified`/`sent`; commit as the source of truth.
- Never `git add -A`; stage by name. Multi-lane: use an isolated worktree + PR to `master`.
- Canon gate: never claim live anything an outsider can't re-derive; x402 is data-only; no token.

_Ordering note: cost only at step 1 (Space upgrade) + optional marketplaces; everything else £0. No step fires on
a raw password._
