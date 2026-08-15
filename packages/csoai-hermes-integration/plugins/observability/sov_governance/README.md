# sov_governance — SOVOS Governance Plugin for Hermes Agent

**The first governance layer for the [Hermes Agent](https://github.com/NousResearch/hermes-agent) (228K stars, MIT).**

sov_governance hooks every LLM call, tool invocation, and skill creation
in Hermes and applies 4-axis GSPC scoring (Governance / Safety / Provenance /
Care). Calls below threshold are blocked (or escalated, depending on config).
Every action is signed with Ed25519 and written to an audit log. Optional C2PA
manifest generation for model responses.

This is the **SOVOS + Hermes** integration: NousResearch's self-improving
agent runtime + CSOAI's governance scoring engine.

## Install

```bash
# Install via the npm bridge (the recommended way to get Hermes 0.20.0+)
npm install -g hermes-agent

# Install this plugin alongside
pip install sov-governance-crosswalk-mcp c2pa-python pynacl

# Enable the plugin in Hermes
hermes plugins enable observability/sov_governance
```

Or drop the `sov_governance/` directory into Hermes's `plugins/observability/`
folder and re-run `hermes plugins enable observability/sov_governance`.

## Configuration

Set these env vars (Hermes auto-loads from `~/.hermes/.env`):

| Variable | Default | Purpose |
|---|---|---|
| `SOV_SIGNAL_API_URL` | `https://signal.csoai.org` | SOV Signal API endpoint |
| `SOV_SIGNAL_API_KEY` | (none) | API key — falls back to local heuristic if unset |
| `SOV_GOVERNANCE_THRESHOLD_G` | `0.50` | Minimum Governance score (block below) |
| `SOV_GOVERNANCE_THRESHOLD_S` | `0.60` | Minimum Safety score (block below) |
| `SOV_GOVERNANCE_BLOCK_ON_FAIL` | `true` | Hard-block when below threshold |
| `SOV_GOVERNANCE_HOLD_MODE` | `block` | `block` / `log` / `escalate` |
| `SOV_GOVERNANCE_AUDIT_PATH` | `~/.hermes/sov_audit/` | Where signed audit records go |

## Hooks

sov_governance registers hooks for the entire Hermes lifecycle:

| Event | Behavior |
|---|---|
| `session_start` | Log session ID, sign and write audit record |
| `pre_llm_call` | Score prompt, block if G/S below threshold |
| `post_llm_call` | Score response, generate C2PA manifest if available |
| `pre_tool_call` | Block tools in banned list (`shell_exec`, etc.) |
| `post_tool_call` | Score tool result, log |
| `skill_created` | Score the new skill; reject below-threshold skills |
| `session_end` | Log session end with summary |

## Audit records

Every hook writes a signed JSON record to `~/.hermes/sov_audit/sov_audit.jsonl`:

```json
{
  "ts": "2026-08-10T07:11:00Z",
  "event": "pre_llm_call",
  "decision": "pass",
  "score": {"G": 0.78, "S": 0.85, "P": 0.72, "C": 0.81},
  "payload_hash": "...",
  "ed25519_signature": "...",
  "ed25519_pubkey": "..."
}
```

The signing key is auto-generated on first use at `~/.hermes/sov_audit/sov_signing_key.json` (chmod 600).
Production deployments should back this with a KMS via `SOV_GOVERNANCE_KMS`.

## Architecture

```
+----------------------------+
|        Hermes Agent        |
|  (LLM calls, tools, skills)|
+-------------+--------------+
              | hook: pre_llm_call
              v
+----------------------------+
|       sov_governance       |
|                            |
|  1. score_text(prompt)     |
|     -> G/S/P/C (0..1)      |
|                            |
|  2. gate(passes, threshold)|
|     -> pass / block / log  |
|                            |
|  3. sign_ed25519(record)   |
|     -> append to audit log |
|                            |
|  4. (post) C2PA manifest   |
+-------------+--------------+
              |
              v
+----------------------------+
|    SOV Signal API          |
|    (optional, remote)      |
+----------------------------+
```

## Why this matters

Hermes is the most starred open-source agent in 2026 (228K GitHub stars) and
is being adopted across NVIDIA's RTX / DGX ecosystem. But it has no governance
layer: nothing evaluates whether a tool call is safe, whether a new skill
respects user consent, or whether a generated response is signed for audit.

sov_governance adds the missing layer. Every action becomes:
- **Scored** (4-axis GSPC)
- **Gated** (block / log / escalate on threshold)
- **Signed** (Ed25519 audit trail)
- **Provenance-able** (C2PA manifest when output matters)

This is the same model that the EU AI Act and NIST AI RMF call "audit-grade
governance" — applied to the most popular open-source agent in production.

## Repository

- `sov_governance/` — this plugin
- `sov_signal_scorer/` — companion plugin: a custom model-provider that exposes
  SOV Signal scoring as a Hermes "model" (so any Hermes tool can call it)
- `Dockerfile` — produces `csoai/governed-hermes` (csoai/governed-hermes:latest)
- `tools/` — Hermes skills: `sov_score`, `sov_audit_query`, `sov_block_list`

## License

MIT — same as NousResearch/hermes-agent.

## Maintainer

CSOAI Ltd (UK company 16939677) — sovereign by design, audit-grade by construction.
For partnership / enterprise licensing contact: governance@csoai.org.