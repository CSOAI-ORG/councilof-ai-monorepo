# csoai-capability-registry

The **canonical sovereign substrate** — typed Python over the JSON registries that drive SOVOS:

| File | What it describes |
|---|---|
| `sovereign-charters/sov33-capability-registry.json` | 33 MCPs · 12 layers (L0..L11) · 12 generals · 5 OWEM groups · 7 hard stops · care_floor=0.95 · quorum 23/33 |
| `SOVOS/data/hive/jspace_deck.json` | 54 J-space cards (the water layer) · 10 axes · 6 piece types · total value=1686 |
| `c_space_card.json` | The folded "honey" C-card · 54 cards → 562 honey units |

## What it ships

- `Registry`, `Layer`, `OwemGroup`, `General`, `Mcp` (sourced from the registry JSON)
- `JSpaceCard`, `JSpaceDeck` (sourced from the J-space deck)
- `CSpaceCard` (the honey distillation)
- `load_registry()`, `load_jspace_deck()`, `load_cspace_card()`
- Query helpers: `get_mcp(name|alias)`, `get_layer(id)`, `get_general(id)`, `tools_for_general / layer / owem`
- `is_hard_stop(behaviour)` — strips "No X or Y (explanation)" negation, then substring-matches against the 7 hard stops

## Canonical numbers (verified 2026-08-11, A100 pod)

| Quantity | Value |
|---|---|
| Layers | 12 (L0..L11) |
| Generals | 12 (the Olympians) |
| OWEM groups | 5 (compliance, defense, intuition, voice, general) |
| MCPs | 33 |
| Tools across all MCPs | **111** |
| Hard stops | 7 |
| Care floor | 0.95 |
| 23/33 council threshold default | 23/33 |
| J-space cards | 54 |
| J-space axes | 10 (ASI, MCP, SWARM, MACH, GOV, AGI, CARE, OSS, DET, PRV) |
| J-space piece types | 6 (Rook, Pawn, Knight, King, Queen, Bishop) |
| J-space total value | 1686.0 |
| C-card honey units | 562 |
| C-card deck_count | 54 |

## Registry inconsistencies caught on load (audit notes)

The registry JSON has **two known inconsistencies** that this package handles but should be canonicalised in the next registry pass:

1. **Case: layer owners are lowercase (`hermes`), generals are title-case (`Hermes`).** Comparison helpers normalise to lowercase.
2. **Layer IDs sort lexicographically (`L0, L1, L10, L11, L2, ...`)** — natural-sort by numeric suffix is required.

Both are documented in the test suite (`test_04b_registry_inconsistency_owners_case_is_known_gap`, `test_18_layers_form_a_complete_L0_to_L11_stack`).

## Quick start

```python
from csoai_capability_registry import load_registry, load_jspace_deck, load_cspace_card

# substrate
r = load_registry()
print(r.care_floor, r.bft_quorum_default)        # 0.95 23/33
print(r.mcp_count, r.layer_count, r.general_count)  # 33 12 12
print(r.tools_for_general(12))                    # Zeus's tool surface

# governance: refuse bad behaviour
if r.is_hard_stop("deploy an autonomous kinetic targeting drone"):
    raise PermissionError("hard stop: kinetic targeting")

# J-space deck (54 water-layer cards)
deck = load_jspace_deck()
print(deck.count, deck.axis_distribution, deck.total_value)
asi = deck.cards_for_axis("ASI")                 # 12 ASI cards

# C-card (folded honey)
card = load_cspace_card()
print(card.deck_count, card.honey_units)         # 54 562
```

## Test status

42/42 green on A100 (`pip install pytest`, run from repo root).