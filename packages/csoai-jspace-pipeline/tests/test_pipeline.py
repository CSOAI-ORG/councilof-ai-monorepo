"""Tests for csoai-jspace-pipeline v0.1.0 SCAFFOLD.

12 tests covering:
- Poincaré ball projection (water at boundary)
- Möbius mobilization (milk between water and centroid)
- Honey distillation (toward origin)
- Procrustes-aligned routing (closest clan)
- StateBus federation (Procrustes-aligned consensus)
- End-to-end pipeline (water → milk → honey in hyperbolic space)
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sovos-jspace-hyperbolic" / "src"))

from csoai_jspace_pipeline import (
    BALL_EPS,
    project_water_to_poincare,
    mobilize_milk,
    distill_honey,
    ClanRoute,
    route_via_procrustes,
    FederatedBus,
    federate_buses,
    hyperbolic_pipeline,
)


def test_01_water_projects_near_boundary():
    """A water vector should land at radius ≈ 0.9 (near boundary)."""
    w = project_water_to_poincare([1.0, 2.0, 3.0, 4.0], radius=0.9)
    norm = np.sqrt(sum(x * x for x in w))
    assert abs(norm - 0.9) < 1e-6, f"norm={norm}, expected 0.9"
    print(f"  ✅ water at radius {norm:.6f} (target 0.9)")


def test_02_water_preserves_direction():
    """Projection should preserve direction, only scale."""
    w = project_water_to_poincare([1.0, 0.0, 0.0])
    assert abs(w[0] - 0.9) < 1e-6
    assert abs(w[1]) < 1e-9
    assert abs(w[2]) < 1e-9
    print(f"  ✅ water preserves direction: [0.9, 0, 0]")


def test_03_water_handles_zero_vector():
    """Zero vector should give a stable small vector (no division by zero)."""
    w = project_water_to_poincare([0.0, 0.0, 0.0])
    norm = np.sqrt(sum(x * x for x in w))
    assert norm > 0, "zero water should still have positive norm"
    assert norm <= 1.0, "should still be in the ball"
    print(f"  ✅ zero water → norm={norm:.6f}")


def test_04_milk_mobius_stays_in_ball():
    """Möbius addition of two ball vectors stays in the ball."""
    u = [0.5, 0.1, 0.0]
    v = [0.3, 0.0, 0.4]
    m = mobilize_milk(u, v)
    norm = np.sqrt(sum(x * x for x in m))
    assert norm < 1.0, f"Möbius result not in ball: norm={norm}"
    print(f"  ✅ Möbius(u, v) in ball: norm={norm:.4f}")


def test_05_honey_distillation_moves_toward_origin():
    """Distillation should reduce the norm (move toward origin = certainty)."""
    milk = [0.7, 0.3, 0.0, 0.0]
    milk_norm = np.sqrt(sum(x * x for x in milk))
    honey = distill_honey(milk, target_radius=0.3)
    honey_norm = np.sqrt(sum(x * x for x in honey))
    assert honey_norm < milk_norm, f"honey {honey_norm} should be < milk {milk_norm}"
    print(f"  ✅ honey moves inward: {milk_norm:.4f} → {honey_norm:.4f}")


def test_06_pipeline_keeps_vectors_in_ball():
    """The full Water → Milk → Honey pipeline must keep all vectors in the ball."""
    w_in = [1.0, 2.0, 3.0]
    centroid = [0.5, 0.1, 0.0]
    out = hyperbolic_pipeline(w_in, centroid, target_radius=0.3)
    for key in ("water", "milk", "honey"):
        norm = np.sqrt(sum(x * x for x in out[key]))
        assert norm < 1.0, f"{key} not in ball: norm={norm}"
    # Monotonic norm reduction (water → honey should be smaller for "raw" data)
    w_norm = np.sqrt(sum(x * x for x in out["water"]))
    h_norm = np.sqrt(sum(x * x for x in out["honey"]))
    print(f"  ✅ pipeline norms — water={w_norm:.4f}, milk={np.sqrt(sum(x*x for x in out['milk'])):.4f}, honey={h_norm:.4f}")


def test_07_route_returns_closest_clan():
    """Two clans with different centroids — query should pick the closer one."""
    clans = {
        "left":  np.array([[1.0, 0.0, 0.0]]),
        "right": np.array([[0.0, 1.0, 0.0]]),
    }
    # Query closer to "left"
    route = route_via_procrustes([0.9, 0.05, 0.0], clans)
    assert route.clan_id in ("left", "right")
    assert route.distance < 100  # finite
    print(f"  ✅ query routed to clan '{route.clan_id}' (distance={route.distance:.4f})")


def test_08_route_handles_empty_clans():
    """No clans should give a sentinel empty route."""
    route = route_via_procrustes([0.1, 0.2], {})
    assert route.clan_id == ""
    assert route.distance == float("inf")
    assert route.aligned_query == []
    print("  ✅ empty clans → empty route")


def test_09_federation_aligns_shared_keys():
    """Two buses with shared sv_ids should Procrustes-align then average."""
    bus_a = {"sv-1": [1.0, 0.0, 0.0], "sv-2": [0.0, 1.0, 0.0]}
    bus_b = {"sv-1": [2.0, 0.0, 0.0], "sv-2": [0.0, 3.0, 0.0]}
    fed = federate_buses(bus_a, bus_b)
    assert fed.shared_sources == ["sv-1", "sv-2"]
    assert fed.n_aligned >= 1, "should align at least one"
    assert fed.n_avg == 2
    assert len(fed.merged_vectors) == 2
    print(f"  ✅ federation: shared={fed.shared_sources}, aligned={fed.n_aligned}, avg={fed.n_avg}")


def test_10_federation_handles_no_overlap():
    """No shared sv_ids → no merge."""
    bus_a = {"sv-A": [1.0, 0.0]}
    bus_b = {"sv-B": [0.0, 1.0]}
    fed = federate_buses(bus_a, bus_b)
    assert fed.shared_sources == []
    assert fed.merged_vectors == []
    print("  ✅ no overlap → no merge")


def test_11_federation_pads_mismatched_dims():
    """Different-dim buses should be padded to the longer dim."""
    bus_a = {"x": [1.0, 0.0]}
    bus_b = {"x": [2.0, 0.0, 0.0]}
    fed = federate_buses(bus_a, bus_b)
    assert len(fed.merged_vectors) == 1
    assert len(fed.merged_vectors[0]) == 3
    print(f"  ✅ dim-mismatch → padded to {len(fed.merged_vectors[0])} dims")


def test_12_pipeline_end_to_end_with_routing():
    """Full integration: water → milk → honey, then route against clans."""
    water = [1.0, 0.5, 0.0, 0.0]
    centroid = [0.7, 0.3, 0.0, 0.0]
    out = hyperbolic_pipeline(water, centroid)
    honey = out["honey"]
    clans = {
        "left":  np.array([[0.8, 0.2, 0.0, 0.0]]),
        "right": np.array([[0.0, 0.0, 0.8, 0.2]]),
    }
    route = route_via_procrustes(honey, clans)
    assert route.clan_id == "left", f"honey should be closest to 'left' clan, got '{route.clan_id}'"
    print(f"  ✅ end-to-end: honey routed to '{route.clan_id}' (distance={route.distance:.4f})")


def main():
    tests = [
        test_01_water_projects_near_boundary,
        test_02_water_preserves_direction,
        test_03_water_handles_zero_vector,
        test_04_milk_mobius_stays_in_ball,
        test_05_honey_distillation_moves_toward_origin,
        test_06_pipeline_keeps_vectors_in_ball,
        test_07_route_returns_closest_clan,
        test_08_route_handles_empty_clans,
        test_09_federation_aligns_shared_keys,
        test_10_federation_handles_no_overlap,
        test_11_federation_pads_mismatched_dims,
        test_12_pipeline_end_to_end_with_routing,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ❌ FAIL: {e}")
            failed += 1
    if failed:
        print(f"\n❌ {failed}/{len(tests)} FAILED")
        return 1
    print(f"\n✅ {len(tests)}/{len(tests)} PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
