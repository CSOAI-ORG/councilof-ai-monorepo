# CSOAI Living Outreach & Connection Registry

**The single source of truth** for all outward outreach + connection work, so every agent (JEEVES, JARVIS,
Claude, Kimi, Cursor) works against **one map** instead of duplicating or clobbering.

- Machine-readable: **`outreach-registry.json`** (read/write this; it is the living DB).
- Human-readable: this file + the audit summary below.
- Content drafts for gated counterparties: **`outreach-drafts/*.md`** (polished, NOT sent).

## How to use (working protocol)
1. **Before ANY publish / send / account-activate:** read `outreach-registry.json`, confirm the row's
   `status` + `owner_gate`, and re-audit the claimed `verified` field. Never double-send to an entry already
   `sent: true` or `LIVE`.
2. **Update one place.** When you change a connection's state, edit the JSON row (status/verified/sent) and
   commit. All other agents read the same file.
3. **Never fabricate a `verified`.** Verified = an HTTP 200 I observed or an in-repo artifact I confirmed.
4. **Canon (binds every row):** scores never sold · regulators free (R8) · x402 is data-only, never scores ·
   no token · ClaimGuard grammar gate · measurement ≠ certification · JL.5 (stranger must re-derive it).

## Current-state audit (2026-08-25, JEEVES)
| Category | Count | Status notes |
|---|---|---|
| Live product surfaces (councilof.ai) | 7 | `/eunomia` `/first-fine-watch` `/eunomia-data` `/sectors` `/registers` + `/api/*` · all 200 |
| Public APIs | 2 | `/api/eunomia-data` (x402 0.02USD data-only), `/api/registers` (10 signed axes CAT F6 REAL) |
| HF live | 3 | gspc-board, gspc-bench-results (datasets), gspc-governance-leaderboard (Space) · public 200 |
| A2A | 2 | agent-card.json (live 200); awesome-a2a PR #157 open |
| MCP | 1 | csoai-axis-engine 8 tools ready; publish gated (name mismatch) |
| Ownership/structure | 13 | axes = 10 MEASURED + 3 UNMEASURED (ai-economy, human-labour, humanoid-labour; PR #645) |
| Outreach counterparties | 4 | PREP-ONLY, none sent (AIUC-1, Armilla, aiSure, Testudo) |
| Board memberships | 6 | C2PA active; OpenSSF/x402/OWASP/AI-Verify pending; BSI ART/1 gated |
| Infra | 3 | A100 DOWN (owner restart); Oracle micros LIVE; overnight launcher LIVE |

## The full connection map (protocol → where it lives)
```
MCP   {csoai-axis-engine.mcp_server}  -> publish `csoai-governance-mcp` 1.0.2 (GATED owner)
A2A   {.well-known/agent-card.json}   -> live; directories = owner web-forms
x402  {csoai-x402-gate}               -> commercial_data lane; never_scores
API   {/api/eunomia-data, /api/registers} -> live; data-only
HF    {csoai/gspc-*}                  -> datasets + Space live; DOIs = owner web-UI
Layer0  {csoai-* monorepo packages}   -> signature/attestation bridge into the instrument
```

## Not doing (deliberately — safety / cost / owner gates)
- **No external sends, no account activation, no publishing** happens from this file. Any entry marked
  `owner_gate` needs Nick's explicit per-action confirmation and the correct channel (many are broker- or
  formal-process distributed, not cold email).
- **No plaintext credentials** are stored in the registry. Activation uses an OAuth/browser session, never a
  raw password.
- **No duplicate publishing** — the audit table + re-audit rule exist precisely to stop parallel agents from
  re-sending or re-building an already-live surface.

_Re-audit before any publish. Update the JSON, not this prose, when state changes._
