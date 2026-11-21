# MCP Registry intake execution receipt

- **Observed:** 2026-09-29 13:29 UTC
- **Owner:** M4 ChatGPT, integration lane
- **Artifact:** `packages/csoai-harvest/` bounded official MCP Registry discovery intake
- **Branch / PR:** `codex/mcp-registry-intake-20260929`, [PR #7](https://github.com/CSOAI-ORG/councilof-ai-monorepo/pull/7)
- **Observed PR state:** open, mergeable, head `f0275fac204c93c8934afeeb4129c2d5d0a58f0a`; no check runs reported
- **Local verification:** 12 focused `unittest` cases pass on Python 3.14.7; compile check and `git diff --check` pass
- **Live endpoint smoke:** 2026-09-29 13:32 UTC, M4 adapter request bounded to 2 rows / 1 page timed out after 15 seconds; direct `curl` to the same official endpoint returned HTTP 000 after 20 seconds with 0 bytes. Independent web fetch was also inaccessible. No registry records were ingested; endpoint reachability is unknown from this environment
- **Remote CI:** manual workflow dispatch returned HTTP 422, `Actions has been disabled for this user`; no CI result is claimed
- **Boundary:** discovery metadata only. No persistence, server execution, GSPC score/admission, signature, timestamp, publication, buyer use, or settlement
- **Status:** prepared; awaiting GitHub Actions restoration and maintainer review
- **Next action / owner:** account owner restores Actions; repository maintainer reviews and decides whether to merge
