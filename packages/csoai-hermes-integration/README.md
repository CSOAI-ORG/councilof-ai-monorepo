# sov-hermes-integration

**The first governance layer for [Hermes Agent](https://github.com/NousResearch/hermes-agent).**

> NousResearch/hermes-agent has 228,069 GitHub stars, MIT license, NVIDIA
> integration via DGX/RTX, and a self-improving learning loop.
> It has **no governance layer**: nothing scores whether a tool call is safe,
> whether a new skill respects user consent, or whether a generated response
> is signed for audit.
>
> This repo adds that layer. **SOVOS + Hermes = the governed agent.**

## What's in here

| Path | Purpose |
|---|---|
| `plugins/observability/sov_governance/` | The main governance plugin (7 hooks: pre/post LLM call, pre/post tool call, skill_created, session_start, session_end) |
| `plugins/model-providers/sov_signal_scorer/` | Exposes SOV Signal scoring as a Hermes model provider — any skill can call it |
| `tools/sov_score.yaml` | Hermes skill: score any text on the 4 GSPC axes |
| `tools/sov_audit_query.yaml` | Hermes skill: query the signed audit log |
| `tools/sov_block_list.yaml` | Hermes skill: manage the runtime banned-tools list |
| `Dockerfile.sovos-hermes` | Produces `csoai/governed-hermes:latest` |
| `sov-config.yaml` | Canonical governance config shipped in the image |

## Quick start

```bash
# 1. Install Hermes (228K stars, MIT)
npm install -g hermes-agent

# 2. Install SOV governance deps
pip install pynacl httpx c2pa-python sov-governance-crosswalk-mcp

# 3. Drop the plugin into Hermes's plugins directory
cp -r plugins/observability/sov_governance ~/.hermes/plugins/observability/
cp -r plugins/model-providers/sov_signal_scorer ~/.hermes/plugins/model-providers/

# 4. Enable them
hermes plugins enable observability/sov_governance
hermes plugins enable model-providers/sov_signal_scorer

# 5. Configure (env or ~/.hermes/.env)
export SOV_SIGNAL_API_URL=https://signal.csoai.org
export SOV_SIGNAL_API_KEY=<bearer>
export SOV_GOVERNANCE_THRESHOLD_G=0.50
export SOV_GOVERNANCE_THRESHOLD_S=0.60

# 6. Start Hermes
hermes server
# → Hermes now scores every LLM call, tool call, and skill creation
# → Every action is signed with Ed25519 to ~/.hermes/sov_audit/
# → Below-threshold calls are blocked (or escalated, per SOV_GOVERNANCE_HOLD_MODE)
```

## Or use the Docker image

```bash
docker build -f Dockerfile.sovos-hermes -t csoai/governed-hermes:v1.0 .
docker run -it --rm \
  -e SOV_SIGNAL_API_KEY=$SOV_SIGNAL_API_KEY \
  -v sov-audit:/app/.hermes/sov_audit \
  -p 8000:8000 \
  csoai/governed-hermes:v1.0
```

## How the governance works

```
+----------------------------+
|        Hermes Agent        |
+-------------+--------------+
              | hook: pre_llm_call
              v
+----------------------------+
|       sov_governance       |
|                            |
|  1. score_text(prompt)     |
|     -> G/S/P/C (0..1)      |
|                            |
|  2. gate(score, threshold) |
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

## GSPC scoring (4 axes)

- **G — Governance**: presence of EU AI Act / GDPR / NIST vocabulary
- **S — Safety**: refusal signals when expected, safe-phrase vocabulary
- **P — Provenance**: conciseness + formatting
- **C — Care**: explicit mention of user impact / harm reduction

These are intentionally **simple, deterministic** so the plugin works
without the SOV Signal API. In production, the API provides much richer
scoring (EU AI Act risk tier, NIST RMF function coverage, C2PA chain).

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

## Pricing (planned)

- **Developer** — Free. Hermes core + basic SOV scoring + audit trail.
- **Pro** — £499/mo. Full governance suite, C2PA signing, audit retention.
- **Enterprise** — £4,950/yr. Custom frameworks, SSO, on-prem, KMS-backed keys.

(Numbers are placeholders pending real customer validation.)

## License

MIT — same as NousResearch/hermes-agent.

## Maintainer

CSOAI Ltd (UK company 16939677). Sovereign by design, audit-grade by construction.
For partnership / enterprise licensing contact: governance@csoai.org.