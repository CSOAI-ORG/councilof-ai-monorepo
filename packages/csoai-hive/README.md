# csoai-hive

The **Fractal Monotric Hive** — Ring-0 AI governance kernel. Same node
structure at every scale: token, agent, clan, cluster, ecosystem.

This package is a hybrid: it ships the **Rust kernel** (the canonical,
compiled subsystem) **alongside a Python interface** so the rest of the
SOVOS monorepo can drive it without writing Rust.

## Provenance

Absorbed 2026-08-11 from `~/clawd/csoai-static-deploy2/sov-hive/`, where
Nick built the kernel before the monorepo convention. The Rust code was
already compiled (`cargo build` clean on the original tree) and has been
**moved verbatim** into `rust-kernel/` here — line-for-line copy.

The operation it backs lives in `~/.hermes/skills/csoai-hive/` via the
Kimi handoffs.

## What's in here

```
csoai-hive/
├── rust-kernel/                        # Rust kernel (verbatim from sov-hive/)
│   ├── Cargo.toml                       # name=sov_hive, ed=2021
│   ├── Cargo.lock                       # 10993 bytes
│   ├── SOVOS_MEMORY.md                  # the live status (2026-08-01)
│   └── src/                             # 11 modules
│       ├── lib.rs                       # SOVOS Fractal Monotric Hive
│       ├── hive.rs                      # HiveNode (fractal monotric cell)
│       ├── drum.rs                      # Continuous simulation engine
│       ├── honey.rs                     # Knowledge creation engine
│       ├── iwm.rs                       # Infinite World Memory (128-bit fractal)
│       ├── jcard.rs                     # J-Space Cards (symbolic knowledge)
│       ├── meta.rs                      # Meta-cognition (family expertise graph)
│       ├── phlabet.rs                   # 256 primal symbols (compression)
│       ├── rainbow.rs                   # Multi-spectral defense (7 layers)
│       ├── spine.rs                     # GNN message passing over Phlabet
│       └── main.rs                      # CLI entry-point
│
├── src/
│   └── csoai_hive/
│       └── __init__.py                 # Python facade (this file)
│
├── data/                                # operational data (from forest/)
│   ├── owem_clan_swarm.json             # clan-mastra / clan-langgraph / clan-ag2 / clan-msaf
│   ├── owem_cluster_config.json         # m4-controller / m2-worker
│   ├── jspace_deck.json                 # 54 J-Space Cards
│   └── tier0_routers.json               # routing config
│
├── modelfiles/                          # OWEM faction modelfiles
│   └── sov6-{abstraction,aesthetics,agency,creation,destruction,
│       embodiment,ethics,identity,logic,preservation,relationality,
│       synthesis,temporality}-v3-light.Modelfile
│
├── withdrawn.py                         # registry of withdrawn models,
│   # consulted by every level of the hive. wraps csoai-hive-withdrawn
│   # runtime checks (see forge).
│
└── tests/                               # to follow
```

## Build / run

The Rust kernel builds standalone:

```
cd rust-kernel/
cargo build --release
./target/release/sov-hive-cli
```

The Python facade is the import path for the rest of SOVOS:

```python
from csoai_hive import (
    Scale,             # TOKEN / AGENT / CLAN / CLUSTER / ECOSYSTEM
    GSPCAxes,          # G-S-P-C scores [gov, security, privacy, commerce]
    HiveNode,          # the fractal cell
    OWEMSwarm,         # the clan swarm registry
    WITHDRAWN_MODELS,  # the immutable registry
    jspace_deck,       # the 54 cards
)
```

Every entity in the hive is a `HiveNode`. The same struct holds for
token, agent, clan, cluster, and ecosystem.

## One-paragraph summary for the operator

A `HiveNode` has 4 GSPC axes ([gov, security, privacy, commerce],
each 0.0–1.0), a `NodeState` (energy, GSPC, kind, is_dreaming,
last_action, recent glyph memory), and fractal children + optional
parent ID. The scale constants are byte-sized:
`SCALE_TOKEN=0, SCALE_AGENT=8, SCALE_CLAN=16, SCALE_CLUSTER=24,
SCALE_ECOSYSTEM=32`. The `IWM` is the 128-bit fractal address
(`[Epoch:32][Scale:16][X:24][Y:24][Z:24][W:8]`). The `Phlabet` is 256
primals used as compression primitives. The `J-Space Cards` are 54
tarot archetypes (5 axes, several piece types, signature sigils
and water/air/fire/earth honey ranks). The `OWEM Swarm` joins
external-agent frameworks as clans: Mastra (agent routing),
LangGraph (compliance orchestration), AG2 (research swarm), MSAF
(enterprise runtime), and more. The withdrawn registry is the
asymmetric gate: every level consults it before routing a query
to a model. Honey is the self-generated knowledge that feeds
back into training. Drum is the off-cycle dream simulation.
Rainbow Security is the 7 layers of multi-spectral defense.

*Ring 0 = Layer 0 = The Monad = The One.*
