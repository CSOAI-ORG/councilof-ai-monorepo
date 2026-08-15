# SOVOS One Mind: An Architectural Skeleton for Governed Multi-Substrate AI

**Authors:** CSOAI Ltd (UK Companies House #16939677) — Nicholas Templeman
**Status:** Pre-print draft, August 2026
**Repository:** `github.com:CSOAI-ORG/csoai-static-deploy2/SOVOS/packages/csoai-mind`

## Abstract

We present the SOVOS One Mind — a 1,000-line Python module that unifies the
state representation, substrate registry, and pipeline orchestration of
a governed AI system. The design rests on three primitives:

1. **`StateBus`** — every agent, tool, quantum state, MCP message, and
   ingested data point exists as a `StateVector` (content-hash ID +
   numerical vector + JSON payload + layer tag). One bus, one memory
   fabric.
2. **`Layer0Fabric`** — CPO photonic links, MCP tools, and A2A agents
   registered as one substrate. Semantic routing by capability-vector
   cosine similarity. Power model from NVIDIA CPO datasheets: 30 W
   conventional → 9 W co-packaged per 1.6T link (70% reduction).
3. **`Water → Milk → Honey` pipeline** — raw ingestion, OWEM hive
   transformation (6-axis: frozen/fluid × left/right × small/big), and
   distilled routing decision. One call: `mind.think(source, payload)`.

The implementation runs on Python 3.10+ with stdlib only (no PyTorch,
no numpy). 10/10 tests pass on both Mac and the RunPod GPU pod.

## 1. Why a One-Mind substrate?

A multi-agent AI system with CPO optics, A2A swarm packets, MCP tool
calls, and quantum-classical hybrid inference has **at least four
incompatible communication fabrics**. Without a unified state substrate,
every cross-fabric message requires bespoke translation, which is the
dominant source of latency and bugs in practice.

The One Mind collapses everything into one type:

```
StateVector = (source, layer, vector, payload)
```

where:
- `source` ∈ {domain, mcp:<tool>, a2a:<agent>, quantum:<circuit>, control:…}
- `layer` ∈ {water, milk, honey, action, control}
- `vector` ∈ R^n — task vector / capability vector / measurement
- `payload` — JSON-serialisable structured data

The `StateBus` stores these. Subscribers receive callbacks when new
vectors land in a layer they care about. The OWEM hive consumes milk
vectors as they appear, without polling.

## 2. Substrate: Layer 0

Three primitives:

### CPOLink — photonic interconnect

Honest numbers (NVIDIA CPO datasheets, 2026):
- Conventional pluggable optical transceiver: ~30 W per 1.6T link
- Co-packaged optics (CPO): ~9 W per 1.6T link
- Latency improvement: tens to hundreds of nanoseconds

`CPOLink.power_savings_vs_pluggable()` returns:
```
{"cpo_power_w": 9, "pluggable_baseline_w": 30, "power_saved_w": 21,
 "power_reduction_pct": 70.0}
```

For N links, `Layer0Fabric.cpo_savings_summary()` aggregates cumulative
savings. **This is a model, not a hardware driver** — the numbers
are real, the simulation is software.

### MCPTool — capability-vector-routed endpoint

```
MCPTool(tool_id, name, description, capability_vector, handler)
```

`match_score(query_vector)` returns cosine similarity. `Layer0Fabric.route(query)`
returns the tool with the highest cosine (ties broken by tool_id).

### A2AAgent — agent on the fabric

```
A2AAgent(agent_id, name, role, state_vector, tools, endpoint)
```

Agents carry their own state_vector and the set of tool_ids they can
call. Inter-agent messages flow through the bus as control-layer
StateVectors.

## 3. Pipeline: Water → Milk → Honey

### Water (raw ingestion)

`WaterIngestion.ingest(source_id, payload)` produces a StateVector on
the `water` layer. The vectoriser is hash-based and deterministic:

```
hash(sha256, payload) → bytes → float in [-1, 1] → pad/normalize to vector_dim
```

Real implementations would use learned embeddings. The hash version is
a stand-in that ensures **the same payload always produces the same
vector** (tested in `test_08_water_vector_is_deterministic`).

### Milk (hive transformation)

`MilkProcessor.process(water_sv)` reads a water vector and applies a
hive transform. Six canonical axes:

| Axis | Operation | Output shape |
|---|---|---|
| LEFT (compress) | project + normalise | target_dim |
| RIGHT (expand) | zero-pad + normalise | target_dim |
| SMALL (local) | normalise | input shape |
| BIG (global) | EMA with running mean | input shape |

Plus `mode ∈ {FROZEN, FLUID}`. FROZEN is deterministic; FLUID updates a
running mean across calls (`mean = 0.9·mean + 0.1·new`).

### Honey (semantic routing decision)

`HoneyDistiller.distill(milk_sv)` runs the milk vector through
`Layer0Fabric.route()`, producing a `Decision(target_tool_id,
confidence, reasoning)`. The Decision is serialised onto a `honey`
StateVector.

### One-call facade

```python
result = mind.think("iokfarm.sensors", {"ph": 7.2, "ammonia_ppm": 0.05})
# result.water_sv_id, result.milk_sv_id, result.honey_sv_id
# result.decision.target_tool_id, result.decision.confidence
```

## 4. Results

10/10 tests pass on both Mac (Python 3.14, stdlib only) and RunPod
sov-brain-2 (Python 3.11, stdlib only).

```
✅ full pipeline: water→milk→honey produces 3 unique sv_ids
✅ bus layers: 1 water, 1 milk, 1 honey per think()
✅ CPO savings: 42 W saved (70% reduction vs pluggable)
✅ routing: a→a, b→b, c→c by cosine similarity
✅ LEFT axis: 8-dim water → 4-dim milk
✅ RIGHT axis: 4-dim water → 8-dim milk
✅ FLUID mode: running mean evolves across calls (diff=0.298)
✅ deterministic: identical payload → identical water vector
✅ subscribe('water') fires for every ingest
✅ iok-farm scenario: 4 ingests → 4 honeys routed to tools
```

## 5. Honest limitations

- **In-memory bus**: no persistence layer. The brief identified this as
  gap #2 (SovRecord storage). Owner-gated — needs Qdrant/Postgres/Redis.
- **Hash-based vectoriser**: real impl would use learned embeddings
  (CLIP, BGE, custom transformer).
- **Synthetic capability vectors**: real impl would train these on
  tool descriptions + usage patterns.
- **No A2A protocol implementation**: Google's A2A spec needs study.
- **No real CPO hardware**: the power/latency numbers are from
  NVIDIA's published CPO datasheets.

## 6. Related work

- LangGraph / LangChain — agent orchestration (different substrate model)
- MCP (Model Context Protocol) — Anthropic, our tool layer uses it
- A2A (Agent-to-Agent) — Google, our agent layer targets it
- NVIDIA CPO — physical layer we model
- PennyLane / MergeKit — math libraries we orchestrate, not replace

## 7. Reproduction

```bash
cd /path/to/SOVOS/packages/csoai-mind
PYTHONPATH=src python3 tests/test_mind.py
```

Expected: `10 passed`.

---

*CSOAI Ltd · UK Companies House #16939677 · Sovereign by Design*
