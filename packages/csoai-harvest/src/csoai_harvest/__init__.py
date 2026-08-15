"""csoai_harvest — License-governed intake machine for the sovereign substrate.

The harvest pipeline (Master Part X.2):
  WATCH  → track GitHub releases from these orgs
  GATE 1 → LICENSE (SPDX allow/deny/quarantine)
  ABSORB → adapter, not fork (wrap upstream, ride releases)
  GATE 2 → ARENA (12 GSPC axes, signed refusal on regression)
  SIGN   → 3KB card (sigil + provenance)
  PUBLISH → SOV Space registry
  RETURN → upstream PRs (catapult both ways)

The GOVERNANCE governs the INTAKE — dogfood at the door. The Rego
policy here is the same kind of policy that gates sovos-article-zero
on outbound actions; here it gates inbound assimilation.

This package ships the WATCH + GATE 1 stages. ABSORB / GATE 2 / SIGN /
PUBLISH / RETURN are downstream packages (csoai-harvest-2, sovos-arena,
sovos-sigil, sovos-charter-registry, sovos-catapult).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


# SPDX allow-list (per Master Part X.1 + Part Y white space)
LICENSE_ALLOW: Set[str] = {
    "Apache-2.0",
    "BSD-3-Clause",
    "BSD-2-Clause",
    "MIT",
    "CC-BY-4.0",
    "CC0-1.0",
    "MPL-2.0",
    "ISC",
    "Zlib",
    "Unlicense",
    # NVIDIA Open Model License — commercially licensable
    "NVIDIA-Open-Model-License",
    # Llama Community License — derivative works OK
    "Llama-3.1-Community",
    "Llama-3.3-Community",
}

# Deny-list (NEVER absorb)
LICENSE_DENY: Set[str] = {
    # AGPL — too viral for sovereign stack
    "AGPL-3.0",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    # SSPL — server-side public license
    "SSPL-1.0",
    # Commons Clause (no commercial)
    "Commons-Clause",
    # Non-commercial variants
    "CC-BY-NC-4.0",
    "CC-BY-NC-SA-4.0",
    "CC-BY-NC-ND-4.0",
}

# Quarantine — absorb only per-component (needs human sign-off)
LICENSE_QUARANTINE: Set[str] = {
    "Open-X-Embodiment",  # 60+ upstream licenses, per-component (Part X.1)
    "Research-Only",
    "Custom",
    "Other",
}


class Verdict(str, Enum):
    ABSORB = "ABSORB"            # clean commercial, take it
    QUARANTINE = "QUARANTINE"    # needs human review per component
    DENY = "DENY"                # reject — viral / non-commercial


@dataclass(frozen=True)
class TrackedOrg:
    """A GitHub org we monitor for new releases to absorb."""
    name: str
    why: str
    repos: List[str] = field(default_factory=list)


# Tracked orgs (Master Part X.1)
TRACKED_ORGS: List[TrackedOrg] = [
    TrackedOrg(
        name="NVIDIA",
        why="Isaac GR00T N1.7 (Apache 2.0 code, commercially licensable weights) — Crown Jewel humanoid brain",
        repos=["Isaac-GR00T", "IsaacLab", "Cosmos", "NeMo"],
    ),
    TrackedOrg(
        name="unitreerobotics",
        why="Full humanoid stack (BSD-3 + open) — G1/H2/R1/Go2/B2, sim2sim, xr_teleoperate",
        repos=[
            "unitree_rl_gym", "unitree_rl_lab", "unitree_sdk2_python",
            "unitree_ros", "unitree_mujoco", "xr_teleoperate", "unifolm-world-model-action",
        ],
    ),
    TrackedOrg(
        name="huggingface",
        why="LeRobot hub (Apache) — robot-learning primitives, datasets, ACT/SmolVLA-450M/π0",
        repos=["lerobot"],
    ),
    TrackedOrg(
        name="openvla",
        why="OpenVLA 7B / Octo generalist policies for OXE cross-architecture merge candidates",
        repos=["openvla", "octo"],
    ),
    TrackedOrg(
        name="google-deepmind",
        why="A2A protocol reference impl, Gemini Robotics (closed but useful for spec adherence)",
        repos=[],
    ),
    TrackedOrg(
        name="arcee-ai",
        why="mergekit (Apache 2.0) — the merging engine; pull every release",
        repos=["mergekit"],
    ),
    TrackedOrg(
        name="facebookresearch",
        why="Sam2 (segment-anything), DROID/SimplerEnv-style research",
        repos=["sam2"],
    ),
    TrackedOrg(
        name="openai",
        why="C2PA, Triton, gpt-oss (per-component license review)",
        repos=["triton"],
    ),
    TrackedOrg(
        name="anthropic",
        why="MCP spec reference, claude code (per-component)",
        repos=[],
    ),
    TrackedOrg(
        name="meta-llama",
        why="Llama 3.3 family (Community License — wrap, not fork)",
        repos=["llama", "llama-cookbook"],
    ),
]


@dataclass(frozen=True)
class HarvestVerdict:
    org: str
    repo: str
    license: str
    verdict: Verdict
    reason: str

    def is_actionable(self) -> bool:
        """ABSORB or QUARANTINE = actionable. DENY = drop."""
        return self.verdict in (Verdict.ABSORB, Verdict.QUARANTINE)


def gate_license(license_id: str, org: str = "", repo: str = "") -> HarvestVerdict:
    """Apply the license gate to one SPDX identifier.

    Returns ABSORB if the license is in the allow-list,
    QUARANTINE if it needs human review, DENY if it must not be absorbed.
    """
    # normalise the SPDX identifier
    norm = license_id.strip()
    if norm in LICENSE_ALLOW:
        return HarvestVerdict(
            org=org, repo=repo, license=norm, verdict=Verdict.ABSORB,
            reason=f"license {norm} on allow-list — clean commercial use",
        )
    if norm in LICENSE_DENY:
        return HarvestVerdict(
            org=org, repo=repo, license=norm, verdict=Verdict.DENY,
            reason=f"license {norm} on deny-list — viral or non-commercial",
        )
    if norm in LICENSE_QUARANTINE:
        return HarvestVerdict(
            org=org, repo=repo, license=norm, verdict=Verdict.QUARANTINE,
            reason=f"license {norm} requires per-component review",
        )
    # unknown license — quarantine by default (Article 0 governs the intake)
    return HarvestVerdict(
        org=org, repo=repo, license=norm, verdict=Verdict.QUARANTINE,
        reason=f"unknown license {norm} — quarantine until review",
    )


def render_regogo_policy() -> str:
    """Render the Rego policy for license gating (mirrors the Python gate).

    Both implementations MUST agree (test_az18 in sovos-article-zero
    enforces this for Article 0; same doctrine here).
    """
    allow_rules = "\n".join([
        f'        "{lic}"' for lic in sorted(LICENSE_ALLOW)
    ])
    deny_rules = "\n".join([
        f'        "{lic}"' for lic in sorted(LICENSE_DENY)
    ])
    quarantine_rules = "\n".join([
        f'        "{lic}"' for lic in sorted(LICENSE_QUARANTINE)
    ])

    return f"""package sovos.harvest.license

# SPDX allow-list — clean commercial licenses we may absorb freely
allow := {{
{allow_rules}
}}

# SPDX deny-list — viral or non-commercial licenses; NEVER absorb
deny := {{
{deny_rules}
}}

# SPDX quarantine-list — needs human review per-component
quarantine := {{
{quarantine_rules}
}}

# verdict(license_id) = "ABSORB" | "QUARANTINE" | "DENY"
verdict(license_id) := "DENY" if {{
    license_id in deny
}} else := "ABSORB" if {{
    license_id in allow
}} else := "QUARANTINE"

# Default-deny posture: unknown license → quarantine, never absorb
"""


__all__ = [
    "LICENSE_ALLOW",
    "LICENSE_DENY",
    "LICENSE_QUARANTINE",
    "TRACKED_ORGS",
    "HarvestVerdict",
    "TrackedOrg",
    "Verdict",
    "gate_license",
    "render_regogo_policy",
]