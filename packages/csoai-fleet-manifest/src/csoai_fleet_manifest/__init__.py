"""csoai_fleet_manifest — the canonical fleet + corpus + surface inventory.

Loads `SOVEREIGN_MASTER_v2.json` (the standing sovereign estate
manifest, last updated 2026-07-30) and exposes its claims as a
typed Python object so the rest of the substrate can cross-check
without parsing JSON.

This is the single source of truth for fleet size, training-data
totals, benchmark status, refutations, and the list of items blocked
on Nick's owner gates.

Honest scope:
  - 90 ollama models (across 5 categories)
  - 8,559 honey corpus
  - 12,193 training samples (34 sources)
  - 193 govbench items × 26 dimensions × 10 models
  - 110 compbench tasks
  - 4 refutations (including 2 RETRACTED)
  - 6 blocked-on-Nick gates

The numbers in this manifest are CANONICAL — they ship as the
substrate's self-description and are referenced from the README,
the spec6 reproducibility test, and the fleet-manifest drain rule
(master Part V: kill the 38/39/26 drift).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


MANIFEST_PATH_DEFAULT = (
    Path(__file__).resolve().parents[5] / "SOVEREIGN_MASTER_v2.json"
)


@dataclass(frozen=True)
class Benchmark:
    name: str
    raw: Dict[str, Any]


@dataclass(frozen=True)
class Claim:
    raw: Dict[str, Any]


@dataclass(frozen=True)
class Surface:
    raw: Dict[str, Any]


@dataclass(frozen=True)
class TrainingData:
    total: int
    sources: int
    domains: Dict[str, int]


@dataclass(frozen=True)
class HoneyCorpus:
    total: int
    formats: List[str]


@dataclass(frozen=True)
class Models:
    total: int
    categories: Dict[str, int]
    clan_names_sample: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FleetManifest:
    version: str
    updated: str
    honey_corpus: HoneyCorpus
    training_data: TrainingData
    models: Models
    benchmarks: Dict[str, Benchmark]
    claims: Dict[str, Claim]
    refutations: List[str]
    security: Dict[str, str]
    surfaces: Dict[str, str]
    blocked_on_nick: List[str]

    # ------------------------------------------------------------------
    # helper methods
    # ------------------------------------------------------------------

    @property
    def benchmark_count(self) -> int:
        return len(self.benchmarks)

    @property
    def benchmark_live_count(self) -> int:
        return sum(1 for b in self.benchmarks.values()
                   if b.raw.get("status") == "LIVE"
                   or b.raw.get("status") == "BUILT")

    @property
    def retracted_claims(self) -> List[str]:
        return [r for r in self.refutations if "RETRACTED" in r]

    @property
    def live_surfaces(self) -> Dict[str, str]:
        out = {}
        for name, url in self.surfaces.items():
            if "(200)" in url:
                out[name] = url
        return out


def load_fleet_manifest(path: Optional[Path] = None) -> FleetManifest:
    p = path or MANIFEST_PATH_DEFAULT
    if not p.exists():
        raise FileNotFoundError(
            f"Fleet manifest not found at {p}. "
            f"Expected SOVEREIGN_MASTER_v2.json in repo root."
        )
    d = json.loads(p.read_text())

    hc = d.get("honey_corpus", {})
    honey = HoneyCorpus(
        total=int(hc.get("total", 0)),
        formats=list(hc.get("formats", [])),
    )

    td = d.get("training_data", {})
    training = TrainingData(
        total=int(td.get("total", 0)),
        sources=int(td.get("sources", 0)),
        domains=dict(td.get("domains", {})),
    )

    md = d.get("models", {})
    models = Models(
        total=int(md.get("total", 0)),
        categories=dict(md.get("categories", {})),
    )

    benchmarks = {k: Benchmark(name=k, raw=v) for k, v in d.get("benchmarks", {}).items()}
    claims = {k: Claim(raw=v) for k, v in d.get("claims", {}).items()}
    surfaces = {k: Surface(raw={k: v}) for k, v in d.get("surfaces", {}).items()}

    return FleetManifest(
        version=d.get("version", ""),
        updated=d.get("updated", ""),
        honey_corpus=honey,
        training_data=training,
        models=models,
        benchmarks=benchmarks,
        claims=claims,
        refutations=list(d.get("refutations", [])),
        security=dict(d.get("security", {})),
        surfaces={k: v for k, v in d.get("surfaces", {}).items()},
        blocked_on_nick=list(d.get("blocked_on_nick", [])),
    )


__all__ = [
    "Benchmark",
    "Claim",
    "FleetManifest",
    "HoneyCorpus",
    "Models",
    "Surface",
    "TrainingData",
    "load_fleet_manifest",
    "MANIFEST_PATH_DEFAULT",
]