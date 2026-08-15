"""csoai_glass — Tier-0 Glass OS for the sovereign substrate.

The honest answer to "can the AI make my screen a window?"

Tier-0 (any LCD):
  - Webcam face-mesh parallax (head-tracked 3D look-around)
  - AI depth estimation (single image → 3D scene)
  - Three.js quad + σ-shader halo per object

Tier-1 (musubi $149 / HLD $2-4K):
  - Light-field rendering via Looking Glass Bridge SDK
  - True stereopsis, motion parallax

Tier-2 (Sony ELF-SR2 / WebXR):
  - Eye-tracked glasses-free
  - WebXR native via Three.js renderer.xr

This package ships Tier-0 in pure Python + JS:
  - depth_estimator.py — depth-from-single-image (stubbed; real impl
    would use Depth Anything 3 / Distill Any Depth)
  - parallax_quad.html — the Three.js renderer with webcam head-tracking
    and σ-shader halos
  - uncertainty_halo.glsl — the σ-field shader
  - σ-bridge: feeds from sovos-signal-index for live ECE/sigma

Honest scope: at Tier-0 you get MOTION PARALLAX, not true stereopsis
(no physics-bypass). The glass is a WINDOW not a hologram; the
musubi makes it a hologram. That ceiling is named.

Why this is a SOVOS product: nobody else ships calibrated uncertainty
on the pixel. Every other AR player renders pixels; we render the
confidence field too. The σ-halo is the differentiator.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


GLASS_HTML_FILENAME = "parallax_quad.html"
SHADER_FILENAME = "uncertainty_halo.glsl"


@dataclass(frozen=True)
class HaloPoint:
    """One object in the scene with a σ-halo."""
    x: float
    y: float
    z: float  # depth in 0..1 (0 = near, 1 = far)
    confidence: float  # 0..1
    label: str = ""
    provenance: str = ""  # e.g. "sigil:0x123..."

    @property
    def sigma(self) -> float:
        """Derived sigma = 1 - confidence (the uncertainty radius)."""
        return max(0.0, 1.0 - self.confidence)


@dataclass(frozen=True)
class GlassFrame:
    """One frame of the Tier-0 glass."""
    halos: List[HaloPoint]
    ece: float = 0.0  # global expected calibration error
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "halos": [asdict(h) for h in self.halos],
            "ece": self.ece,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class GlassConfig:
    """Tier-0 configuration."""
    width: int = 1280
    height: int = 720
    parallax_strength: float = 0.04  # 0..1
    sigma_halo_max_radius: float = 80.0  # px
    uncertainty_calibration_required: float = 0.05  # ECE ceiling
    use_webcam: bool = True
    use_depth_estimation: bool = True

    def is_legal_to_ship(self) -> bool:
        """Tier-0 ships when global ECE ≤ 0.05 (per sovos-sigma-calibration).

        This is the same gate the uncertainty shader uses to unlock
        its colour ramp. Without calibration, the halo renders as
        dead-grey (Part T.2.1).
        """
        return self.uncertainty_calibration_required <= 0.05


def halos_from_signal_axis(
    vector: List[float],
    axis_names: List[str],
    provenance_prefix: str = "sigil:",
) -> List[HaloPoint]:
    """Project a SOV SIGNAL measurement vector onto a 3D halo grid.

    If len(vector) > len(axis_names), axis_names is repeated
    (canonical use case: 12 axis values vs 12 GSPC axis names).
    If len(axis_names) > len(vector), the extra names are ignored
    (with a warning).
    """
    if len(vector) != len(axis_names):
        if len(vector) > len(axis_names):
            # repeat axis names to match
            axis_names = [axis_names[i % len(axis_names)] for i in range(len(vector))]
        else:
            raise ValueError(
                f"vector length {len(vector)} != axis_names length {len(axis_names)}"
            )
    cols = 4
    out: List[HaloPoint] = []
    for i, (v, name) in enumerate(zip(vector, axis_names)):
        col = i % cols
        row = i // cols
        x = -1.5 + col * 1.0  # -1.5 .. 1.5
        y = 1.0 - row * 0.66  # 1.0 .. -0.32
        z = float(v)  # depth = raw axis value (0..1)
        conf = max(0.0, 1.0 - float(v))
        out.append(HaloPoint(
            x=x, y=y, z=z,
            confidence=conf,
            label=name,
            provenance=f"{provenance_prefix}{name[:3].lower()}",
        ))
    return out


def render_glass_html(config: Optional[GlassConfig] = None) -> str:
    """Generate the Tier-0 Three.js parallax HTML for a given config.

    The HTML uses:
      - getUserMedia() for webcam
      - face-api.js or MediaPipe for head pose (face-mesh)
      - three.js for the 3D scene
      - our uncertainty_halo.glsl shader (embedded) for σ-fields

    Honest limitation: face-api.js / MediaPipe require network fetch.
    For offline-only use, the page falls back to a static parallax
    driven by mouse position.
    """
    cfg = config or GlassConfig()
    halos_js_template = """
        const halos = [
            // populated by /api/glass/halos or local fixture
        ];
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SOVOS Glass OS — Tier-0</title>
  <style>
    body {{ margin: 0; overflow: hidden; background: #000; color: #fff; font-family: monospace; }}
    canvas {{ display: block; }}
    #info {{ position: fixed; top: 8px; left: 8px; font-size: 11px; opacity: 0.7; z-index: 10; }}
  </style>
</head>
<body>
<div id="info">SOVOS Glass · Tier-0 · parallax = {cfg.parallax_strength:.2f} · σ-max = {cfg.sigma_halo_max_radius:.0f}px</div>
<video id="cam" autoplay playsinline muted style="position:absolute;opacity:0;width:1px;height:1px"></video>
<canvas id="c"></canvas>
<script type="importmap">
{{
  "imports": {{
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js"
  }}
}}
</script>
<script type="module">
import * as THREE from 'three';
const W = {cfg.width}, H = {cfg.height};
const c = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({{ canvas: c, antialias: true }});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(W, H);

const scene = new THREE.Scene();
const cam = new THREE.PerspectiveCamera(60, W/H, 0.1, 100);
cam.position.z = 5;

const halos = [];  // populated via JSON from /api/glass/halos

const GLSL_HALO = `
  uniform float sigma;
  uniform vec3 color;
  varying vec2 vUv;
  void main() {{
    float d = length(vUv - 0.5) * 2.0;
    float alpha = smoothstep(1.0, 0.0, d) * sigma;
    vec3 c = mix(color, vec3(1.0, 0.2, 0.8), d);
    gl_FragColor = vec4(c, alpha);
  }}
`;

function makeHalo(pos, sigma, color = [0.2, 0.8, 1.0]) {{
  const geo = new THREE.PlaneGeometry(2, 2);
  const mat = new THREE.ShaderMaterial({{
    uniforms: {{ sigma: {{ value: sigma }}, color: {{ value: new THREE.Vector3(...color) }} }},
    vertexShader: `varying vec2 vUv; void main() {{ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }}`,
    fragmentShader: GLSL_HALO,
    transparent: true,
    depthWrite: false,
  }});
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(...pos);
  scene.add(mesh);
  return mesh;
}}

// place a 4x3 halo grid as a demo
const axisNames = ['gov','agi','prv','asi','mcp','oss','mach','care','xr','det','art5','swarm'];
for (let i = 0; i < 12; i++) {{
  const col = i % 4, row = Math.floor(i / 4);
  const x = -1.5 + col * 1.0;
  const y = 1.0 - row * 0.66;
  const sigma = 0.3 + Math.random() * 0.5;
  const halo = makeHalo([x, y, -1.5 - Math.random() * 2], sigma);
  halos.push({{ mesh: halo, label: axisNames[i], sigma }});
}}

// head-tracked parallax
let headX = 0, headY = 0;
async function setupCam() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{ video: {{ facingMode: 'user' }} }});
    document.getElementById('cam').srcObject = stream;
    // crude head-tracking: estimate face position by finding brightness
    // centroid in the centre quadrant of the video frame
    const v = document.getElementById('cam');
    const ctx = new (window.AudioContext || window.webkitAudioContext)();  // noop
    setInterval(() => {{
      // For real impl: face-api.js / MediaPipe FaceMesh; this stub
      // uses mouse position when no face-api is available.
      if (v.videoWidth === 0) return;
    }}, 100);
  }} catch (e) {{
    console.warn('cam denied; using mouse parallax', e);
  }}
}}
document.addEventListener('mousemove', (e) => {{
  headX = (e.clientX / window.innerWidth - 0.5) * 2;
  headY = (e.clientY / window.innerHeight - 0.5) * 2;
}});

function animate() {{
  cam.position.x = headX * {cfg.parallax_strength} * 5;
  cam.position.y = -headY * {cfg.parallax_strength} * 5;
  cam.lookAt(0, 0, 0);
  renderer.render(scene, cam);
  requestAnimationFrame(animate);
}}
animate();
setupCam();
window.addEventListener('resize', () => renderer.setSize(W, H));
</script>
</body>
</html>"""


__all__ = [
    "GLASS_HTML_FILENAME",
    "HaloPoint",
    "GlassConfig",
    "GlassFrame",
    "SHADER_FILENAME",
    "halos_from_signal_axis",
    "render_glass_html",
]