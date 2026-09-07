# CSOAI Owner Fire-Book — activation & sends (fire-ready, v2)

> **2026-08-26 status:** HF DOIs DONE · PR #645 + #788 merged + LIVE · RunPod pods ALL down (console restart) ·
> browser-only items below, each with exact URL + steps (research-verified 2026-08-26).
> Full research brief: `csoai-static-deploy2/SOVOS/DISTRIBUTION_FIREBOOK_2026-08-26.md`.

**How this works:** Nick opens each session; I prepare the exact content + verify before/after. No plaintext
password; no bulk blast; no duplicate send (living DB = `outreach-registry.json`).

---

## 1 · MCP Registry publish — £0 (the name fix is now known)
The mismatch fix: npm package name stays `csoai-governance-mcp`; add **`"mcpName": "io.github.CSOAI-ORG/gspc"`**
to package.json — they are decoupled.
1. package.json: add `mcpName` (snippet in `fire-ready/mcp-package.json.snippet`).
2. `npm publish` (npm account, free).
3. `brew install mcp-publisher` → `mcp-publisher init` → server.json (see `fire-ready/mcp-server.json`).
4. `mcp-publisher login github` → GitHub device-flow (https://github.com/login/device + code).
5. `mcp-publisher publish` → verify via `https://registry.modelcontextprotocol.io/v0.1/servers?search=gspc`.
- [ ] Nick: run the device-flow + publish (or I drive the CLI if he grants a session). Verify after.

## 2 · A2A directories — £0
- **a2aagentlist.com** (NOT .ai): submission is an **email to gal6111@gmail.com**, subject "A2A Agent Submission",
  incl. agent details + card URL. Draft ready: `fire-ready/a2aagentlist-email.md`. ⚠️ personal gmail, community-run.
- **a2a-registry.org**: submit (no account, /submit) or publish (auth, /console/agents, STAGE→ACTIVE).
- **artinet**: NOT a directory (open-source A2A platform, the-artinet-project/artinet) — skip listing.
- [ ] Nick: send the a2aagentlist email + submit to a2a-registry.org.

## 3 · awesome-a2a — £0
- Canonical repo is **github.com/ai-boost/awesome-a2a** (goatapi/awesome-a2a does NOT exist — the earlier
  PR #157 was likely on the wrong repo; re-target). Entry format: `*   🔗 [Resource Title](link) - one-sentence description`;
  add to README section AND mirror in README_zh.md; fork→branch→commit (`✨ Add: ...`)→PR.
- Draft entry ready: `fire-ready/awesome-a2a-entry.md`.
- [ ] Nick (or I via API with his GH session): fork, add entry, PR.

## 4 · Datarade — £0 entry (30% commission on free tier)
- Apply: **https://providers.datarade.ai/apply** (3-min form) → review 1–2 business days → Provider Studio.
- Publishing policies: datarade.ai/company/publishing-policies. Free tier = $0/yr + 30% commission; Bronze $6k/yr + 20%.
- [ ] Nick: complete the apply form (copy ready in registry drafts).

## 5 · AWS Data Exchange — £0 to list (+ referral fee on paid)
- "AMMP" = AWS Marketplace Management Portal: aws.amazon.com/marketplace/management.
- Steps: AWS account → AMMP "Register now" → public profile → (paid: W-8/VAT/US bank/Hyperwallet) → open AWS
  Support case requesting Data Exchange qualification → create product/revision/dataset/offer.
- [ ] Nick: AMMP register + support case.

## 6 · Snowflake Marketplace — £0 to list (+ fees on paid, ~15%)
- No web form — **Snowsight** (app.snowflake.com) → Marketplace → Provider Studio → Create Listing.
- Prereqs: FULL account (not trial); **ACCOUNTADMIN or custom role (ORGADMIN delegates privileges to ACCOUNTADMIN first)**;
  accept Provider & Consumer Terms; approved provider profile; paid listings need Stripe Express.
- [ ] Nick: provider profile approval + listing.

## 7 · Boards/standards memberships — free-contribute is the £0 path
- **OpenSSF model-signing (AI/ML Security WG)**: participate FREE (Slack/GitHub/open meetings, openssf.org/community).
  Formal membership: General $5–10k; Associate $0 (nonprofit only — CSOAI LTD doesn't qualify). → **Join WG free**.
- **LF x402 Foundation**: technical participation £0 (Slack slack.x402.org, GitHub x402-foundation/x402, open WGs).
  Formal: Premier $200k; General fee-bearing; Associate $0 (nonprofit). → **Participate free**.
- **OWASP MCP Top-10**: contribute free (fork → PR, "even a line counts"); leadership needs ~$50/yr OWASP membership.
- **AI Verify Foundation (IMDA)**: community £0 (aiverifyfoundation.sg/community); General fee unpublished (contact form).
- **BSI ART/1** (UK mirror ISO/IEC SC 42): committee seat £0, BUT **BSI membership required first** (subscription,
  7 categories, £ varies — contact membership@bsigroup.com). Verify hcms page in browser.
- [ ] Nick: submit WG join requests + AI Verify contact form; decide on BSI membership.

## 8 · Insurance outreach (drafts ready, none sent)
AIUC-1/Schellman (formal) · Armilla (broker, hello@armilla.ai) · Munich Re aiSure (via Mosaic/Syndicate 1609) ·
Testudo (broker). Drafts: `registry/outreach-drafts/*.md`.

## 9 · A100 restart (measurement volume)
RunPod console restart of pod `l7g747oivyq6ab` (`sovos-light-master-mine-20260816`). All RunPod SSH endpoints
timed out 2026-08-26 — console-only. I verify inference before re-running the grind.

## 10 · Cost cheat-sheet (research-verified)
| Item | Cost |
|---|---|
| MCP registry · a2aagentlist · a2a-registry · awesome-a2a · OWASP contribute · OpenSSF WG · x402 technical | **£0** |
| Datarade | £0 + 30% commission (free tier) |
| AWS Data Exchange / Snowflake | £0 to list + fees on paid offers |
| OWASP leadership / BSI membership / OpenSSF General / x402 General / AIVF General | paid (varies) |
| HF Space upgrade (Gradio) | the only hard-money product item |

_Re-audit registry before any publish; no duplicate send; canon gates (never a score sold, x402 data-only, no token)._
