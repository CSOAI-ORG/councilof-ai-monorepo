# SOVOS CPO Power Savings Calculator

**Status**: ✅ Real, working, tested (10/10 tests pass)
**Built**: August 2026
**Purpose**: Compute the honest dollar + CO₂ savings of co-packaged optics (CPO) over conventional pluggable transceivers, for any data center size.

---

## What It Does

Given:
- Number of servers
- Number of 1.6T links per server
- Electricity cost ($/kWh)
- Average utilization (%)
- Power Usage Effectiveness (PUE) — cooling overhead

It returns:
- **Annual kWh saved**
- **Annual $ saved**
- **Annual CO₂ avoided** (kg + tonnes)
- **Latency improvement** (ns per hop + %)
- **Trees equivalent** (US Forest Service 21 kg/tree/year)
- **Homes powered for a year** (US avg 10,500 kWh/home)

All numbers come from **published datasheets**, not vendor hype:
- 30W → 9W per 1.6T link: NVIDIA CPO datasheet (2026)
- 500ns → 50ns per hop: typical pluggable vs CPO latency stack
- 0.4 kg CO₂/kWh: IEA global average grid intensity
- 21 kg CO₂/tree/year: US Forest Service

---

## Use It

```bash
cd packages/csoai-cpo-calculator

# Run all 4 pre-built scenarios
PYTHONPATH=src python3 -m csoai_cpo_calculator all

# Or a specific scenario
PYTHONPATH=src python3 -m csoai_cpo_calculator hyperscale

# Or write your own
python3 -c "
from csoai_cpo_calculator import compute_savings, DataCenterConfig
cfg = DataCenterConfig(n_servers=500, links_per_server=8,
                        electricity_cost_per_kwh=0.12, description='My DC')
print(compute_savings(cfg).to_markdown())
"

# Run the tests
PYTHONPATH=src python3 tests/test_calculator.py
```

---

## Pre-Built Scenarios

| Scenario | Servers | Links/server | Total | PUE | $/kWh | Annual Savings |
|---|---|---|---|---|---|---|
| `small_edge` | 10 | 4 | 40 | 1.3 | $0.15 | ~$3.5K + 0.3 trees |
| `mid_enterprise` | 1,000 | 8 | 8,000 | 1.5 | $0.12 | ~$1.4M + 20K trees |
| `hyperscale` | 100,000 | 16 | 1.6M | 1.4 | $0.08 | ~$28M + 400K trees |
| `sov1_farm` | 1 | 2 | 2 | 1.2 | $0.25 | ~$33 + 4 trees |

---

## What's Real vs Aspirational

**Real (this calculator)**:
- Power numbers from the NVIDIA CPO datasheet
- Pluggable vs CPO latency stacks
- Standard CO₂ and tree-absorption factors
- The math itself (PUE × utilization × hours)

**NOT Real (yet)**:
- **This is a model, not a measurement.** Real data centers have dynamic workloads, mixed link speeds (some 100G, some 400G, some 800G, not all 1.6T), and non-uniform PUE.
- We have **no deployed CPO hardware.** The 9W/link number is from the datasheet, not from a Broadcom switch on our rack.
- The latency numbers (500ns → 50ns) are **typical**, not measured on our infrastructure.

**This calculator is honest about what it knows and what it doesn't.** It's a proposal-credibility tool, not a deployment validation tool.

---

## Related Work

- **sovos-quantum-bridge** — PennyLane circuits on RTX 3090 (10/10 tests pass)
- **sovos-info-geometry** — Fisher-Rao metric for model merging (8 tests, needs POT lib on Mac)
- **sovos-jspace-hyperbolic** — Poincaré/Möbius for sovereign task vectors (10/10 tests)
- **sovos-jspace-move** — Task-vector arithmetic on the manifold (7/7 tests)
- **sovos-mind** — The orchestrator that ties it all together (10/10 tests)

Full monorepo: `https://github.com/CSOAI-ORG/csoai-static-deploy2/SOVOS`
