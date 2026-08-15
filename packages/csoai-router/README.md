# csoai-router

Routing + fleet + cluster orchestration for SOVOS. Absorbed
2026-08-11 from top-level Python scripts that were the operational
spine of the substrate before the monorepo absorbed it.

## Files

| File | Purpose | LOC |
|---|---|---|
| `sov4_router.py`     | Per-suite routing across the OWEM cluster; routes every request to the cheapest/fastest OWEM that excels at the suite | 1195 |
| `sov_orchestrator.py`| SOV-Space unified orchestrator: wires routers, pipelines (23 scripts), training data, models, stigmergy | 242 |
| `sov_swarm.py`       | GPU cluster auto-scaler for sovereign end-user models (tier-0 qwen2.5:0.5b → tier-3 lora-merged) | 255 |
| `master_hives.py`    | Three master OWEM groups (CSOAI / DEFONEOS / DEFENCE / MEOK) as monotonic fractal clusters | 179 |
| `owem_cluster.py`    | The OWEM cluster config + routing keys + heartbeat | 272 |
| `router_control.py`  | Confound-aware router eval (separates the router from the wrapper; Δ+9.42 n=186 result) | 152 |
| `fleet_dashboard.py` | Fleet state observability view | 118 |
| `fleet_monitor.py`   | Heartbeat-based fleet liveness check |  43 |
| `fleet_power.py`     | Computes effective compute power across the heterogeneous fleet | 126 |

## Provenance

All 9 scripts are absorbed verbatim from the top-level of the repo
into `SOVOS/packages/csoai-router/src/csoai_router/`. The package
re-exports them via `__init__.py`.

## Use

```python
from csoai_router import sov4_router, sov_orchestrator
sov4_router.run()
sov_orchestrator.wire_all()  # wires routers, pipelines, models
```

Or run the scripts standalone:

```bash
python3 SOVOS/packages/csoai-router/src/csoai_router/sov4_router.py --help
python3 SOVOS/packages/csoai-router/src/csoai_router/fleet_monitor.py
```

## Cross-link

- The orchestrator's wiring of `sov_router` → pipelines feeds into
  `sovos-arena` (13-axis measurement) + `sovos-chain` (Fisher-Rao
  compliance chain).
- `fleet_dashboard.py` reads from `SOVOS/data/hive/` operational
  JSON (the absorbed `forest/` data).
- `master_hives.py` knows about `CSOAI / DEFONEOS / DEFENCE / MEOK`
  as the three top-level hive brands.

*This is the spine. Each routing decision SOVOS makes passes through
this package.*
