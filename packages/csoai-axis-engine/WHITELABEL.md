# EUNOMIA White-Label Measurement Kit — "we hand working tooling, not blog text"

The pivot: **CSOAI does not just publish measurements — it hands regulators, AI
companies, insurers, bond desks and COBOL parties a *working, pluggable* GSPC/EUNOMIA
tool they can drop onto their own surface to self-audit E2E.** Every run is
Ed25519-signed + EAT-chained + recompute-able; the UI never interprets, it renders
what the predicate did. Measurement, not certification.

## What you get
| Surface | What it does | How to add it |
|---|---|---|
| **MCP server** (`csoai_axis_engine.mcp_server`) | `eunomia.axes` · `eunomia.measure_axis` · `eunomia.verify_card` · `eunomia.crosswalk_articles` | any MCP agent (Claude/GPT/Hermes) calls it |
| **A2A card** | signed Ed25519 attestation per measurement (EAT box 3) | agent→agent attestation |
| **API / 402 gate** | `EUNOMIA_402_URL` — monetise each audit run | per-invocation payment hook |
| **AG-UI / Council OS** | the renderer surfaces the signed board to end-users | embed on your site |

## White-label config (env)
```
EUNOMIA_CLIENT="Your Regulator / Company / Insurer"   # the party's name
EUNOMIA_BRAND="Your Council OS"                        # your branding
EUNOMIA_402_URL="https://pay.yourdomain/x402"          # 402 payment hook
EUNOMIA_KEY=/path/to/your-ed25519.key                  # signing key
EUNOMIA_PORT=8786
```

## Run
```bash
uv run python -m csoai_axis_engine.mcp_server     # stdio MCP (default)
# or as a hosted endpoint:
uv run python -m csoai_axis_engine.mcp_server --host 0.0.0.0  (FastMCP transport)
```

## Example usage (any MCP client)
- `eunomia_axes()` → the 10 financial-verification axes + frozen item counts.
- `eunomia_measure_axis("bond-router", "qwen2.5:7b")` → accuracy + Wilson CI, signed.
- `eunomia_crosswalk_articles("credit-scoring AI", "qwen2.5:7b")` → maps the system to
  EU AI Act articles (art 5/6/9/13/14/15/50) + a sample governance measurement — the
  **"find every problem before you even contact the client"** audit.
- `eunomia_verify_card(card)` → offline-recompute content_id + signature (loginless, free).

## Why this wins
LMArena is *taste*, OpenRouter is *aggregation*. Neither gives a **verifiable, signed,
recompute-able, frozen-item-set** measurement you can drop into a regulator's workflow.
This is the **verification layer** — and it's white-labelable + monetisable (402),
so we don't just preach compliance, we *hand them the machine* that finds it.
