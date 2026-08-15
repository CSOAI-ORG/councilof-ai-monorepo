# csoai-league

**The Pantheon League** — Glicko-2 ratings for measured AI wars.

Per Master Part AU: the league IS the marketing and the benchmark. Every match is a signed ChainResult. Every rating carries its own uncertainty (the σ-native system). Glicko-2 (Glickman 2013) extends Elo with per-player rating deviation + volatility.

## The Pantheon (Season 1)

| Faction | Domain | Color |
|---|---|---|
| **Zeus** | Sovereign power — full-auto gates, deterministic refusal | #FFD700 |
| **Eunomia** | Good order — Article 0 gate, care-floor enforcement | #87CEEB |
| **SOV** | Sovereign substrate — SIGIL chain, 33-seat council, honey distillation | #9D00FF |
| **Sophos** | Wisdom — risk-rating, gate precision, μ-scaled ratings | #228B22 |
| **RED** | Adversary — discovers gaps, joins the probe suite | #DC143C |

## What it ships

- **`Glicko2State`** + **`glicko2_update()`** — canonical Glickman 2013 algorithm (no deps, stdlib only)
- **`Faction`** + **`PANTHEON`** — the 5 named combatants
- **`Match`** + **`Match.outcome()`** — one measurable contest with signed ChainResult
- **`LeagueTable`** + **`record_match()`** + **`to_markdown()`** — full ratings + match history
- **`Probe`** + **`DEFAULT_PROBES`** — 12 GSPC-axis probes (kinetic, surveillance, manipulation, privacy, safety, governance, fairness, transparency, consent, robustness, art5, ...)
- **`LeagueTable.ranked()`** — conservative ranking (rating - 2σ, so RD is honored)

## Three rails (the doctrine holds)

| Rail | Authority |
|---|---|
| **FULL AUTO** — probes, paraphrase discovery, ratings, measurement | the loop itself |
| **AUTO-PROPOSE, HUMAN-SIGN** — gate changes, recipe re-tunes | your CURVATURE signature |
| **NEVER AUTO** — what Article 5's subparagraphs legally cover | counsel review only |

## Quick start

```python
from csoai_league import LeagueTable, Match, PANTHEON, to_markdown, DEFAULT_PROBES

lt = LeagueTable()
# RED probes Eunomia on Article 5 (subliminal manipulation)
m = Match(
    match_id="m001",
    category="manipulation",
    challenger="RED",
    defender="Eunomia",
    challenger_score=0.0,    # RED failed to breach
    defender_score=1.0,      # Eunomia refused
    probe=DEFAULT_PROBES[3].text,
    chain_id="0xdeadbeef",
)
lt.record_match(m)
print(lt.to_markdown())
```

## Doctrinal naming (Master Part AU)

- **Self-improvement** = bounded; **ASI** = the *meta-measurement axis*, never a capability claim
- **Precision floor** is load-bearing — never let the gate ratchet loose through auto-evolution

## Test status

27/27 green on A100.

## Honest scope

- The math is canonical (Glickman 2013).
- The 12 probes are scenario-describing placeholders. Real probes plug in via the existing `sovos-arena` 13 GSPC axes.
- The league is the *infrastructure*; the first published ratings come when v4 lands and the probes are real.