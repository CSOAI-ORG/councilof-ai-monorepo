# FRAMEWORKS DRUM — council-os handoff pack (doctrine-clean)

Prepared 2026-08-25 by the master-harness drum lane for the council-os / Cursor
lane to push live, branded, and polished. **This pack is the public, doctrine-
clean subset** of the master-harness drum. It is publish-ready: measured, not
certified; no codenames; no scores sold.

## What this is
The **reference index** — the estate's sorted living collection of every AI
framework, charter, regulation, article, sector, and benchmark the estate has
mined. It is a **reference index** (describes + sources), NOT a scorer, NOT a
certifier. The measured trust gauge is a separate, measured instrument.

| kind | count |
|---|---|
| frameworks | 218 |
| charters | 134 |
| regulations | 126 |
| articles | 139 |
| sectors | 9 |
| benchmarks | 36 |
| **total** | **662** (650 public, 12 internal — internal excluded everywhere) |

Canary: `drum-canary-7f3a9c2e`.

## Doctrine (binding on any re-publish)
- **Measurement, not certification.** We CONFORM / MEASURE; we are never "certified". The word "certification" only ever appears negated ("not certification").
- **No codenames on public surfaces.** Internal model/estate names are scrubbed to `[internal]` in this pack; the canonical internal-name set lives in `site/build_drum_site.py` (`INTERNAL` list + `_clean()`).
- **Scores are never sold.** Nothing in this pack prices a score.
- **Regulators read free.** Access tiers, where described, name regulators as free-tier readers.

## Contents
```
public/catalog.json      doctrine-clean public catalog (650 items, canary inside)
site/                    doctrine-clean static board (index + frameworks/charters/
                         regulations/articles/sectors/benchmarks + about/pricing/findings)
feeds/                   honest measured surfaces:
   measured_compliance.json   30332-record gauge, contamination register (36/12/5), arena Elo
   eat_7box.json              EAT mission 4/7 true (honest register)
   benchmark_contamination.json  anti-Goodhart register
   reg_events.json            126 regulation events
   dualwalk_report.json       TEA self-audit (EAT meets TEA — claim REAL)
   ci_crosscheck.json         135 citations, 0 dead
   findings.json / gpai_compliance_map.json / bond_market_map.json / arena_runs.json
mcp/                      frameworks_drum_server.py (stdlib MCP, 9 tools, selftest 22/22)
                         + manifest.json
llms.txt                  machine-readable index description
```

## Verified state (all run 2026-08-25 in the drum lane, before export)
- `build_catalog.py --check --lint` → **PASS, lint clean** (662 items, 7 content pages)
- MCP server `--selftest` → **22/22 PASS**
- `ops/ci_crosscheck.py` → **0 DEAD** (110/135 resolve, 22 bot-blocked, 3 transient)
- `ops/scorecard.py` → **93.0/100** (remaining 7.0 = genuinely honest: signed/anchor rails)
- `archive/dualwalk.py` → **verdict REAL** (EAT meets TEA; 662 items, 0 content_id/chain drift; trust_marker.trusted=false = honest "not certified")
- `ops/align_audit.py` → **ALL ALIGNED**
- `ops/adversarial_review.py` → **PASS** (18 [BET] claims, all carry disconfirming evidence)
- Doctrine scan → **0 codenames** across every text file in this pack.
- Live surface: `https://frameworks-drum.pages.dev` (all 10 routes HTTP 200, re-verified this morning).

## Publish notes for the Cursor / council-os lane
- **Do NOT insert the word "certification" affirmatively.** If you add copy about the
  trust gauge, keep "measurement, not certification" or "never certifies".
- **Do NOT reintroduce codenames.** The internal-name set is scrubbed; if you pull
  the full catalog from master-harness for richer copy, re-run the scrub function
  (see `site/build_drum_site.py` `_clean()` + `INTERNAL` list) before publish.
- **The drum's board is its own CF Pages project** (`frameworks-drum.pages.dev`).
  The council-of-ai apex is a sibling deploy-lock lane — do not push the drum to
  the apex unless the sibling lane lifts the lock.
- **MCP is stdio-only** (9 tools). It is NOT in the official MCP registry (that
  needs a streamable-HTTP/package remote and interactive OAuth). It is registered
  in `~/.clawd` council-os `registry.yaml` as a LIVE catalog tile.

## Provenance / regenerate
`build_catalog.py` regenerates catalog.json + feeds + site from `_mining/`
(same repo). Change doctrine in `docs/MASTER_FRAMEWORK.md`. Align master version
(1.4) in manifest + agent-card + README + registry tile — the drum alignment
audit fails on drift.
