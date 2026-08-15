# csoai-mind — One Mind, One StateBus, One Pipeline

**The orchestrator that ties everything in SOVOS together.**

## What it is

The `SovosMind` class is the single facade for SOVOS. It holds:
- A **`StateBus`** — every agent, tool, quantum state, MCP message, A2A swarm packet, and ingested data point lives as a `StateVector` in unified memory.
- A **`Layer0Fabric`** — CPO photonic links, MCP tools, and A2A agents as one substrate. Resolves semantic routing via capability-vector cosine similarity.
- A **`WaterIngestion`** → **`MilkProcessor`** → **`HoneyDistiller`** pipeline. Every state moves through the three named layers.

One method — `mind.think(source_id, raw_payload)` — runs the full pipeline and returns a `ThinkResult` (water → milk → honey sv_ids + decision + bus stats).

## Module map

| File | Class | What it does |
|---|---|---|
| `state.py` | `StateBus`, `StateVector` | Unified memory fabric, content-hash IDs, layer/source indices, subscribe hooks |
| `layer0.py` | `Layer0Fabric`, `CPOLink`, `MCPTool`, `A2AAgent` | Substrate registry, semantic routing via capability vectors, CPO power model (30W → 9W per link) |
| `water.py` | `WaterIngestion`, `IngestionSource` | Raw data → StateVector on the `water` layer, hash-based deterministic vectoriser |
| `milk.py` | `MilkProcessor`, `HiveConfig` | 6-axis OWEM hive transforms (frozen/fluid × left/right × small/big) |
| `honey.py` | `HoneyDistiller`, `Decision` | Semantic routing → tool decision, confidence score, reasoning |
| `mind.py` | `SovosMind`, `ThinkResult` | The facade — wires everything together |

## Run it

```bash
cd /path/to/SOVOS/packages/csoai-mind
PYTHONPATH=src python3 tests/test_mind.py
```

Expected: `✅ 10/10 tests PASSED`

## Tests

1. `test_01_full_pipeline_one_think` — WaterIngestion → MilkProcessor → HoneyDistiller end-to-end
2. `test_02_state_bus_layers_correct` — bus correctly counts layers
3. `test_03_cpo_power_savings` — 2 CPO links save 42 W (70% reduction vs pluggable)
4. `test_04_route_selects_highest_cosine` — routing picks tool with max cosine
5. `test_05_milk_compress_axis` — LEFT hive compresses to target_dim
6. `test_06_milk_expand_axis` — RIGHT hive expands to target_dim
7. `test_07_milk_fluid_mode_updates_running_mean` — FLUID mode learns online
8. `test_08_water_vector_is_deterministic` — same payload → same water vector
9. `test_09_subscribe_fires_on_water` — subscribe hook receives callbacks
10. `test_10_full_scenario_iok_farm_emergency` — 4 successive ingests produce 4 honeys

## Honest scope

This is **architectural skeleton code**, not production-ready:
- No real persistence (the StateBus is in-memory; gap #2 from the brief)
- No real CPO hardware (the power model is from NVIDIA CPO datasheets)
- No real A2A protocol (Google A2A spec needs study)
- No learned capability vectors (synthetic for now)
- No real quantum bridge integration (separate `sovos-quantum-bridge` package handles that)

## License

MIT — CSOAI Ltd (UK 16939677)