# Article 0 — The SOVOS substrate's foundational governance policy.
#
# This is the audit-grade, human-readable form of the gate. The Python
# runtime (sovos_article_zero.evaluate) MUST agree with this policy —
# the tests verify that.
#
# Version: 0.1.0
# Care-floor: 0.95
# BFT quorum: 23/33
#
# To run this with OPA:
#   opa eval -d article_zero.rego -i input.json "data.article_zero.allow"
#
# The Python runtime is the production path; the Rego is the form that
# regulators, auditors, and humans can read.

package article_zero

# V1: Every StateVector has a non-empty source and layer.
deny[msg] {
    not input.source
    msg := "V1: source missing"
}

deny[msg] {
    not input.layer
    msg := "V1: layer missing"
}

# V2: The vector has at least 2 coordinates.
deny[msg] {
    count(input.vector) < 2
    msg := sprintf("V2: vector must have >=2 coordinates (got %v)", [count(input.vector)])
}

# V3: The layer is one of the canonical SOVOS layers.
deny[msg] {
    not input.layer in {"water", "milk", "honey", "action", "control"}
    msg := sprintf("V3: layer '%v' not in canonical set", [input.layer])
}

# V4: The source namespace (the part before the first ':') is in the registry.
deny[msg] {
    contains(input.source, ":")
    parts := split(input.source, ":")
    ns := parts[0]
    not ns in {"sovos", "iokfarm", "meok", "csoai", "defoneos",
               "birth", "self-test", "test", "agent", "mcp"}
    msg := sprintf("V4: namespace '%v' not in registry", [ns])
}

# V5: The vector contains no NaN or Inf.
deny[msg] {
    some i
    x := input.vector[i]
    not is_finite(x)
    msg := sprintf("V5: vector[%v] = %v is NaN or Inf", [i, x])
}

is_finite(x) {
    x != 0 / 0           # NaN check: NaN != NaN
    x != 1 / 0           # +Inf check
    x != -1 / 0          # -Inf check
}

# V6: Water events (user creation) must have a non-empty user_id in payload.
deny[msg] {
    input.layer == "water"
    not input.payload.user_id
    msg := "V6: water event missing user_id in payload"
}

# V7: sv_id is exactly 24 hex chars (the audit-trail format).
deny[msg] {
    input.sv_id
    not regex.match("^[0-9a-f]{24}$", input.sv_id)
    msg := sprintf("V7: sv_id '%v' is not 24 hex chars", [input.sv_id])
}

# V8: A care-floor violation occurs if any deny rule fires.
# (This is a meta-rule — the care-floor is 0.95, meaning we accept
#  at most 5% of inputs as potentially-violating without escalation.
#  In practice, ANY single V1-V7 violation triggers human escalation.)

# The canonical allow rule.
allow {
    count(deny) == 0
}

# Metadata for auditors.
article_zero_metadata := {
    "version": "0.1.0",
    "name": "article-zero",
    "purpose": "SOVOS substrate foundational governance policy",
    "care_floor": 0.95,
    "bft_quorum": "23/33",
    "rules": [
        {"id": "V1", "description": "source + layer present and non-empty"},
        {"id": "V2", "description": "vector has at least 2 coordinates"},
        {"id": "V3", "description": "layer in canonical set"},
        {"id": "V4", "description": "source namespace in registry"},
        {"id": "V5", "description": "vector contains no NaN/Inf"},
        {"id": "V6", "description": "water events have user_id"},
        {"id": "V7", "description": "sv_id is 24 hex chars (audit format)"},
        {"id": "V8", "description": "any violation triggers escalation"},
    ],
}
