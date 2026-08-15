# csoai-glass

**Tier-0 Glass OS** — the honest answer to "can the AI make my screen a window?"

Yes, with a named ceiling: you get **motion parallax** on any LCD, true stereopsis requires optics (musubi $149 / HLD $2-4K).

## What it ships

- `GlassConfig`, `GlassFrame`, `HaloPoint` — typed scene model
- `halos_from_signal_axis(vector, axis_names)` — projects a 13-axis GSPC measurement onto a 4×3 halo grid
- `render_glass_html(config)` — generates the Tier-0 Three.js parallax HTML
- σ-halo shader (embedded in HTML) — uncertainty field per object
- CalibrationGate (ECE ≤ 0.05) — refuses to ship until the σ-field is calibrated

## Tier ladder (per Master Part T)

| Tier | Hardware | What you get | Status |
|---|---|---|---|
| **0** | Any LCD + webcam | Head-tracked parallax + σ-halo | **THIS PACKAGE** |
| 1 | Looking Glass musubi $149 / HLD $2-4K | Light-field rendering | future |
| 2 | Sony ELF-SR2 / WebXR | Eye-tracked glasses-free | future |
| 3 | UE5-class portal | Convergence Portal | separate (Part I) |

## The honest ceiling (Master Part U.1)

> A normal LCD gives motion parallax, not true stereopsis — physics requires optics.

So: **Tier-0 = a window. Tier-1 = a hologram.** Pitch: *"your screen becomes a window; the musubi makes it a hologram."*

## What SOVOS adds that no display player has

- **σ-halo per object** — calibrated confidence field rendered in 3D (nobody else ships this)
- **C2PA provenance per voxel** — the glass knows what it's showing
- **Article 0 gaze-gating** — the constitutional overlay survives the portal
- **Worldline scrubbing** — the 4D time dimension (Part T.2)

## Quick start

```python
from csoai_glass import halos_from_signal_axis, render_glass_html, GlassConfig

# project a measurement
axes = ["gov","agi","prv","asi","mcp","oss","mach","care","xr","det","art5","swarm"]
halos = halos_from_signal_axis([0.3]*12, axes)

# render the HTML
cfg = GlassConfig(parallax_strength=0.05, sigma_halo_max_radius=80.0)
html = render_glass_html(cfg)
open("parallax_quad.html", "w").write(html)
```

## Test status

16/16 green on A100.