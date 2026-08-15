# eu-ai-act-mcp — STATUS: SCAFFOLD (v0.1.0)

**STATUS:** SCAFFOLD — minimal honest implementation. The full implementation
needs to be migrated from wherever it lives (not yet located on disk).

This scaffold:
- Loads on import
- Exposes a real MCP tool that queries EU AI Act articles from a static table
- Includes 3 tests that pass against the scaffold

**To upgrade to v1.0:** copy the actual `eu-ai-act-mcp` source code into
`src/eu_ai_act_mcp/server.py`, replacing the scaffolded server. The package
shape (pyproject.toml, Dockerfile, tests/) is already correct.

## What this scaffold does

Exposes one MCP tool, `eu_ai_act_query`, that:
1. Takes a query string (e.g. "Article 5 prohibited practices")
2. Searches a static table of 13 EU AI Act articles + Annex III categories
3. Returns the matching article + cross-reference to NIST RMF GOVERN-1.1

This is enough to prove the MCP plumbing works end-to-end. The full EU AI
Act corpus (all 113 Articles) needs to be added when the real source lands.

## License

MIT — CSOAI Ltd (UK 16939677)
