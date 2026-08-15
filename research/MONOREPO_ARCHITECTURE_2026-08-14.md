# Council of AI — monorepo architecture (2026-08-14)
#
# ONE source of truth. Everything public (PyPI, npm, HF, Kaggle, 569 GitHub repos,
# Cloudflare Pages) is a GENERATED MIRROR from this monorepo's atom store.
#
# Naming: "Council of AI" (councilof-ai) = masterbrand. MEOK = consumer brand.
# Internal codenames (SOVOS, sov6, OWEM, etc.) NEVER appear in public output.

## Structure
councilof-ai/
├── apps/                  # Deployable applications
│   ├── site/              # councilof.ai React frontend (→ Cloudflare Pages)
│   ├── meok/              # meok.ai consumer landing (→ CF Pages)
│   └── docs/              # API docs, whitepapers
├── packages/              # The measurement kernel (57→~40, rationalized)
│   ├── core/              # sovos-core → council-core (measurement primitives)
│   ├── arena/             # sovos-arena → council-arena
│   ├── league/            # sovos-league → council-league
│   ├── city/              # sovos-city → council-city
│   ├── signal-index/      # sovos-signal-index → council-signal
│   ├── glass/             # sovos-glass → council-glass
│   ├── harvest/           # sovos-harvest → council-harvest
│   ├── person/            # sovos-persona → council-persona
│   ├── fleet/             # sovos-fleet → council-fleet
│   ├── chain/             # sovos-chain → council-chain
│   ├── inspect-bridge/    # sovos-inspect-bridge → council-inspect
│   ├── ras/               # sovos-robot-ras → council-robot-ras
│   ├── dream/             # sovos-dream → council-dream
│   ├── jspace/            # sovos-jspace-* → council-jspace
│   ├── fisher-rao/        # sovos-fisher-rao → council-fisher-rao
│   ├── gprobe/            # sovos-gprobe → council-gprobe
│   ├── asi-evolve/        # sovos-asi-evolve → council-asi-evolve
│   ├── bus-redis/         # sovos-bus-redis → council-bus
│   ├── x402/              # sovos-x402-gate → council-x402
│   └── protocols/         # ProtocolBank → council-protocols
├── charter/               # The 52-article sovereign charter
├── registry/              # Fleet registry, capability registry, numbers registry
├── ops/                   # CI/CD, deploy configs, cron
│   ├── deploy/            # CF Pages, PyPI, npm publish scripts
│   ├── mirror/            # Generated-mirror pipeline (569 org repos)
│   └── cron/              # Overnight queue, autonomous continuation
├── evidence/              # Signed card corpus, longitudinal data
├── research/              # White papers, briefs (for arXiv, DSIT, etc.)
├── AGENTS.md              # Agent rules
├── pyproject.toml         # Monorepo editable install
└── README.md

## Generation rules
- apps/* and packages/* are SOURCE OF TRUTH — edited by human/agent
- All public surfaces (PyPI, npm, HF, Kaggle, GitHub org repos) are GENERATED
- Generation pipeline: monorepo → build → mirror → publish
- The 569 CSOAI-ORG repos are read-only generated mirrors of packages/apps
- Never git add -A (multi-lane repo)