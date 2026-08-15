"""Rego policy for the harvest license gate (mirrors Python)."""
package sovos.harvest.license

# SPDX allow-list — clean commercial licenses we may absorb freely
allow := {
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "CC-BY-4.0",
        "CC0-1.0",
        "ISC",
        "MIT",
        "MPL-2.0",
        "NVIDIA-Open-Model-License",
        "Unlicense",
        "Zlib",
}

# SPDX deny-list — viral or non-commercial; NEVER absorb
deny := {
        "AGPL-3.0",
        "AGPL-3.0-only",
        "AGPL-3.0-or-later",
        "CC-BY-NC-4.0",
        "CC-BY-NC-ND-4.0",
        "CC-BY-NC-SA-4.0",
        "Commons-Clause",
        "SSPL-1.0",
}

# SPDX quarantine-list — needs human review per-component
quarantine := {
        "Custom",
        "Open-X-Embodiment",
        "Other",
        "Research-Only",
}

# verdict(license_id) = "DENY" | "ABSORB" | "QUARANTINE"
verdict(license_id) := "DENY" if {
    license_id in deny
} else := "ABSORB" if {
    license_id in allow
} else := "QUARANTINE"

# Default-deny posture: unknown license → quarantine, never absorb
default_verdict(_) := "QUARANTINE"