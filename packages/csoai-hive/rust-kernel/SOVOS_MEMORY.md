# SOVOS Memory Layer — live status (2026-08-01)

What's actually running, verified, no myth.

## ✅ Live and tested

| Component | Where | Status |
|---|---|---|
| **sov-hive (Rust kernel)** | `~/clawd/csoai-static-deploy2/sov-hive` | `cargo build` ✅ — phlabet/spine/honey/iwm/rainbow/jcard modules |
| **agentmemory server** | `localhost:3111` (`npx @agentmemory/agentmemory`) | HEALTHY — 263 fns. Save+search roundtrip verified. API: `POST /agentmemory/remember`, `POST /agentmemory/smart-search` |
| **cognee 1.4.1** | `~/.cache/csoai/sovos-venv` | Installed ✅. NOTE: v1 API = remember/recall/forget; auth+multi-tenant ON by default (set `ENABLE_BACKEND_ACCESS_CONTROL=false` for local) |
| **mem0** | same venv | Installed ✅ |
| **Local models** | Ollama :11434 | sov-sovereign-v4, sov33-v7, qwen2.5-mined-honey... (Nick's own mined weights) |

## ⏳ Pending

| Item | Gate |
|---|---|
| cognee cognify smoke test | needs embeddings (nomic-embed-text pulling via ollama) + LLM (Groq key ready) |
| NVIDIA NIM free key | Nick: build.nvidia.com signup (email only, ~2 min) — 1,000 free credits, 40 RPM |
| agentmemory auto-start | currently manual `npx`; add LaunchAgent if wanted |
| Graphiti | needs Neo4j (docker) — defer until Cognee proves out |

## Fact-check on the pasted briefing (what was real vs hallucinated)

- REAL: agentmemory (rohitg00, 53 MCP tools, npx), cognee, mem0, graphiti, NVIDIA NIM free tier (1k credits/40 RPM), neurokernel (Columbia, fruit-fly brain, open source)
- UNVERIFIED/LIKELY INFLATED: "Kimi K3 1-bit 594GB", "SOV protocol 12 cranial nerves", EU €10B gigafactories details, "LeWorldModel/V-JEPA 2" availability, most of the mystical framing
- The estate's own honest position: memory layer = agentmemory (running) + cognee (installed) + sov-hive Rust kernel (compiles). Build only what's missing: GSPC scoring glue + Phlabet.

## Disk note (2026-08-01)

Mac disk hit 100% during install. Reclaimed ~6GB: npm cache, pip cache, uv builds, and
`csoai-static-deploy2/.backups` (5.5G, trashed-then-freed — timestamped edit-safety snapshots,
redundant with live tree). uv archive briefly broke (session python) — repaired via
`uv tool install --force kimi-cli`. Watch disk; cognee venv ~2GB.
