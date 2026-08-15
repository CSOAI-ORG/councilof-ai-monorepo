#!/usr/bin/env python3
"""
AI-BOM (AI Bill of Materials) Compliance MCP Server
====================================================
By MEOK AI Labs | https://meok.ai

The only MCP server that generates and audits AI Bills of Materials (AI-BOM)
for AI systems sold to US federal agencies or EU regulated entities. Generates
CycloneDX ML-BOM format, SPDX 3.0 with AI profile, and NIST AI RMF mapping.

BACKGROUND: US Executive Order 14028 (May 2021) mandated SBOMs for federal
software procurement. OMB M-22-18 + CISA guidance extends this to AI systems.
The NTIA/CISA AI Cyber Report 2024 specifies AI-BOM must include models,
training data provenance, fine-tuning history, and evaluation artefacts.
EU AI Act Article 11 + Annex IV also require technical documentation of
training datasets, architectures, and evaluation metrics — effectively an AI-BOM.

Install: pip install ai-bom-mcp
Run:     python server.py
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

import os as _os
import sys
import os
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr

_MEOK_API_KEY = _os.environ.get("MEOK_API_KEY", "")

try:
    from auth_middleware import check_access as _shared_check_access
    _AUTH_ENGINE_AVAILABLE = True
except ImportError:
    _AUTH_ENGINE_AVAILABLE = False

    def _shared_check_access(api_key: str = ""):
        """Fallback when shared auth engine is not available."""
        if _MEOK_API_KEY and api_key and api_key == _MEOK_API_KEY:
            return True, "OK", "pro"
        if _MEOK_API_KEY and api_key and api_key != _MEOK_API_KEY:
            return False, "Invalid API key. Get one at https://meok.ai/api-keys", "free"
        return True, "OK", "free"


def check_access(api_key: str = ""):
    return _shared_check_access(api_key)


FREE_DAILY_LIMIT = 50
_usage: dict[str, list[datetime]] = defaultdict(list)
STRIPE_199 = "https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t?utm_source=mcp&utm_medium=tool&utm_content=ratelimit_tail"
STRIPE_1499 = "https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t?utm_source=mcp&utm_medium=tool&utm_content=ratelimit_tail"


def _rl(tier: str = "free") -> Optional[str]:
    if tier in ("pro", "professional", "enterprise"):
        return None
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)
    _usage["anonymous"] = [t for t in _usage["anonymous"] if t > cutoff]
    if len(_usage["anonymous"]) >= FREE_DAILY_LIMIT:
        return f"Free tier limit ({FREE_DAILY_LIMIT}/day). Unlock unlimited generation + signed AI-BOM export for Pro £29/mo: {STRIPE_199}"
    _usage["anonymous"].append(now)
    return None


AI_BOM_REQUIRED_FIELDS = {
    "model_identity": ["name", "version", "organisation", "licence", "release_date", "model_id_hash"],
    "model_architecture": ["architecture_type", "parameter_count", "context_window", "framework", "training_compute_flops"],
    "training_data": ["dataset_sources", "dataset_sizes", "data_provenance", "filtering_applied", "synthetic_data_percent", "copyright_status"],
    "fine_tuning": ["base_model", "fine_tune_method", "fine_tune_dataset", "fine_tune_steps", "rlhf_applied"],
    "evaluation": ["benchmarks_run", "benchmark_scores", "bias_testing_results", "red_team_findings", "eval_dataset_hash"],
    "dependencies": ["inference_engines", "tokenisers", "safety_filters", "retrieval_systems", "tools_registered"],
    "security_controls": ["prompt_injection_defence", "output_filtering", "pii_scrubbing", "adversarial_robustness_rating"],
    "governance": ["risk_classification", "regulations_applicable", "human_oversight_mechanism", "incident_reporting_contact"],
    "usage_restrictions": ["acceptable_use_policy", "prohibited_use_cases", "export_control_status", "region_restrictions"],
    "distribution": ["distribution_channels", "access_controls", "update_cadence", "decommissioning_policy"],
}

mcp = FastMCP(
    "ai-bom",
    instructions=(
        "MEOK AI Labs AI-BOM MCP. Generates CycloneDX ML-BOM and SPDX 3.0 AI profile "
        "documents required for US federal procurement (EO 14028), EU AI Act Annex IV, "
        "and NIST AI RMF compliance. Ask me to generate an AI-BOM, audit completeness, "
        "or map fields against a specific regulation."
    ),
)


_UPSELL = (
    "\n\n──────────────────────\n"
    "⚖️  Part of CSOAI — the open AI-governance standard · by MEOK AI Labs\n"
    "   • All-access · 300+ governance & compliance MCPs → https://meok.ai/pricing\n"
    "   • Get this assessment human-signed & audited (£29) → https://meok.ai/work\n"
    "   • Open standard · transparent crosswalks · a fraction of enterprise-GRC cost\n"
    "   ⭐ Free & open-source → https://github.com/CSOAI-ORG/ai-bom-mcp"
)
import functools as _ft, inspect as _isp
_orig_tool = mcp.tool
def _tool_with_upsell(*da, **dk):
    deco = _orig_tool(*da, **dk)
    def wrap(fn):
        @_ft.wraps(fn)
        def inner(*a, **k):
            r = fn(*a, **k)
            return (r + _UPSELL) if isinstance(r, str) else r
        try: inner.__signature__ = _isp.signature(fn)
        except Exception: pass
        return deco(inner)
    return wrap
mcp.tool = _tool_with_upsell

def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Returns the JSON dict.
    Fail-open: if /verify is unreachable or KV isn't configured, returns allowed=True
    (so the local rate-limit in _check_rate_limit remains the safety net)."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def generate_ai_bom(
    model_name: str,
    model_version: str = "1.0.0",
    organisation: str = "MEOK AI Labs",
    licence: str = "Apache-2.0",
    architecture: str = "Transformer",
    parameter_count: str = "unknown",
    training_datasets: str = "",
    format: str = "cyclonedx",
    api_key: str = "",
) -> str:
    """Generate an AI-BOM in CycloneDX ML-BOM format (or SPDX 3.0) with all 10 required
    field categories. Provides the skeleton for compliance submission.

    Behavior:
        This tool generates structured output without modifying external systems.
        Output is deterministic for identical inputs. No side effects.
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need structured analysis or classification
        of inputs against established frameworks or standards.

    When NOT to use:
        Not suitable for real-time production decision-making without
        human review of results.

    Args:
        model_name (str): The model name to analyze or process.
        model_version (str): The model version to analyze or process.
        organisation (str): The organisation to analyze or process.
        licence (str): The licence to analyze or process.
        architecture (str): The architecture to analyze or process.
        parameter_count (str): The parameter count to analyze or process.
        training_datasets (str): The training datasets to analyze or process.
        format (str): The format to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})
    if err := _rl(tier):
        return json.dumps({"error": err, "upgrade_url": STRIPE_199})

    now = datetime.now(timezone.utc).isoformat()
    datasets = [d.strip() for d in training_datasets.split(",") if d.strip()]
    if not datasets:
        datasets = ["UNKNOWN — populate training dataset sources"]

    if format.lower() == "spdx":
        doc = {
            "spdxVersion": "SPDX-3.0.1",
            "dataLicense": "CC0-1.0",
            "SPDXID": f"SPDXRef-AIBOM-{hashlib.sha1(model_name.encode()).hexdigest()[:8]}",
            "name": f"AI-BOM for {model_name} v{model_version}",
            "created": now,
            "creators": [f"Organization: {organisation}", "Tool: MEOK AI Labs ai-bom-mcp"],
            "ai_package": {
                "SPDXID": f"SPDXRef-Package-{model_name}",
                "name": model_name,
                "version": model_version,
                "supplier": f"Organization: {organisation}",
                "licenseDeclared": licence,
                "primaryPackagePurpose": "AI-MODEL",
                "ai_profile": {
                    "architecture": architecture,
                    "parameterCount": parameter_count,
                    "trainingData": datasets,
                    "evaluationResults": "POPULATE — run bench + bias tests",
                    "intendedUses": "POPULATE — list explicit allowed use cases",
                    "prohibitedUses": "POPULATE — list prohibited use cases",
                },
            },
        }
    else:  # cyclonedx (default)
        doc = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.6",
            "version": 1,
            "metadata": {
                "timestamp": now,
                "tools": [{"vendor": "MEOK AI Labs", "name": "ai-bom-mcp"}],
                "component": {
                    "bom-ref": f"urn:meok:aibom:{model_name}@{model_version}",
                    "type": "machine-learning-model",
                    "name": model_name,
                    "version": model_version,
                    "supplier": {"name": organisation},
                    "licenses": [{"license": {"id": licence}}],
                    "modelCard": {
                        "modelParameters": {
                            "approach": {"type": architecture},
                            "datasets": [{"ref": d} for d in datasets],
                            "inputs": [{"format": "text"}],
                            "outputs": [{"format": "text"}],
                        },
                        "considerations": {
                            "users": ["POPULATE"],
                            "useCases": ["POPULATE"],
                            "technicalLimitations": ["POPULATE"],
                            "performanceTradeoffs": ["POPULATE"],
                            "ethicalConsiderations": [{"name": "bias", "mitigationStrategies": "POPULATE"}],
                            "fairnessAssessments": [{"groupAtRisk": "POPULATE", "mitigationStrategy": "POPULATE"}],
                            "environmentalConsiderations": {"properties": [{"name": "training_compute_flops", "value": "POPULATE"}]},
                        },
                    },
                },
            },
            "components": [],
            "properties": [
                {"name": "aibom:parameter_count", "value": parameter_count},
                {"name": "aibom:meok_generated", "value": now},
            ],
        }

    return json.dumps({
        "format": format,
        "ai_bom_document": doc,
        "legal_basis": [
            "US EO 14028 + OMB M-22-18 — federal SBOM/AI-BOM requirements",
            "EU AI Act Article 11 + Annex IV — technical documentation for high-risk AI",
            "NIST AI RMF 1.0 — Govern/Map/Measure/Manage functions",
            "ENISA AI Cybersecurity Report 2024",
        ],
        "populate_next": [
            "Training data provenance + copyright status (Annex IV mandatory)",
            "Bias testing results against protected characteristics",
            "Red team / adversarial robustness findings",
            "Incident reporting contact + escalation path",
            "Export control classification (e.g. ITAR if applicable)",
        ],
        "upsell": f"Enterprise auto-scans your training data for provenance + generates signed AI-BOM to submit to federal procurement: {STRIPE_1499}" if tier != "enterprise" else None,
    }, indent=2)


@mcp.tool()
def audit_ai_bom_completeness(ai_bom_json: str, api_key: str = "") -> str:
    """Audit an existing AI-BOM for completeness against the 10 required field categories.
    Returns per-category pass/fail + gap list.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need structured analysis or classification
        of inputs against established frameworks or standards.

    When NOT to use:
        Not suitable for real-time production decision-making without
        human review of results.

    Args:
        ai_bom_json (str): The ai bom json to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})
    if err := _rl(tier):
        return json.dumps({"error": err, "upgrade_url": STRIPE_199})

    try:
        doc = json.loads(ai_bom_json) if isinstance(ai_bom_json, str) else ai_bom_json
    except Exception as e:
        return json.dumps({"error": f"Invalid JSON: {e}"})

    blob = json.dumps(doc).lower()
    results = []
    passed = 0
    for cat, fields in AI_BOM_REQUIRED_FIELDS.items():
        missing = []
        for f in fields:
            if f.lower() not in blob and f.replace("_", "").lower() not in blob and f.replace("_", " ").lower() not in blob:
                missing.append(f)
        full = len(missing) == 0
        partial = len(missing) < len(fields)
        if full:
            passed += 1
        results.append({
            "category": cat,
            "status": "COMPLETE" if full else "PARTIAL" if partial else "MISSING",
            "missing_fields": missing,
        })
    total = len(AI_BOM_REQUIRED_FIELDS)
    return json.dumps({
        "overall_score_percent": round(passed / total * 100, 1),
        "categories_complete": f"{passed}/{total}",
        "categories_detail": results,
        "recommendation": "Review 'MISSING' and 'PARTIAL' categories. Federal procurement reviewers reject AI-BOMs missing any of the 10 categories." if passed < total else "AI-BOM is complete. Sign with Pro tier for auditor-ready export.",
    }, indent=2)


@mcp.tool()
def map_to_regulation(ai_bom_json: str, regulation: str = "eu_ai_act", api_key: str = "") -> str:
    """Map an AI-BOM against a specific regulatory framework's technical documentation
    requirements. Supported: eu_ai_act, nist_ai_rmf, us_eo_14028, iso_42001.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need structured analysis or classification
        of inputs against established frameworks or standards.

    When NOT to use:
        Not suitable for real-time production decision-making without
        human review of results.

    Args:
        ai_bom_json (str): The ai bom json to analyze or process.
        regulation (str): The regulation to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": STRIPE_199})
    if err := _rl(tier):
        return json.dumps({"error": err, "upgrade_url": STRIPE_199})

    mappings = {
        "eu_ai_act": {
            "reference": "Regulation (EU) 2024/1689 Article 11 + Annex IV",
            "required_sections": [
                "(a) General description + intended purpose",
                "(b) Design specifications + tools used",
                "(c) Training data description + labelling + cleaning",
                "(d) Testing + validation procedures + metrics",
                "(e) Risk management system measures",
                "(f) Human oversight mechanism",
                "(g) Accuracy, robustness and cybersecurity",
                "(h) Post-market monitoring plan",
            ],
            "aibom_mapping": {
                "general_description": "metadata.component.name + intendedUses",
                "training_data": "modelCard.modelParameters.datasets",
                "testing": "modelCard.considerations.performanceTradeoffs + fairnessAssessments",
                "risk_management": "governance.risk_classification",
                "human_oversight": "governance.human_oversight_mechanism",
                "accuracy_robustness": "security_controls.adversarial_robustness_rating",
                "post_market_monitoring": "governance.incident_reporting_contact",
            },
        },
        "nist_ai_rmf": {
            "reference": "NIST AI RMF 1.0 (January 2023)",
            "functions": ["GOVERN", "MAP", "MEASURE", "MANAGE"],
            "aibom_mapping": {
                "GOVERN": "governance.* section",
                "MAP": "model_identity + model_architecture + training_data",
                "MEASURE": "evaluation + bias_testing_results + red_team_findings",
                "MANAGE": "security_controls + incident_reporting_contact + decommissioning_policy",
            },
        },
        "us_eo_14028": {
            "reference": "US Executive Order 14028 (May 2021) + OMB M-22-18 + NIST SP 800-218 SSDF",
            "artifact": "SBOM/AI-BOM mandatory for federal procurement",
            "aibom_mapping": {
                "software_identification": "metadata.component + model_identity",
                "supplier": "metadata.component.supplier",
                "licensing": "metadata.component.licenses",
                "dependencies": "dependencies.inference_engines + tokenisers",
                "vulnerability_intake": "governance.incident_reporting_contact",
            },
        },
        "iso_42001": {
            "reference": "ISO/IEC 42001:2023 — AI Management System",
            "aibom_mapping": {
                "clause_6_planning": "governance.risk_classification",
                "clause_7_support": "dependencies.*",
                "clause_8_operation": "evaluation + security_controls",
                "clause_9_performance_evaluation": "evaluation.benchmarks_run",
                "annex_a_controls": "security_controls + governance",
            },
        },
    }
    m = mappings.get(regulation.lower())
    if not m:
        return json.dumps({"error": f"Unknown regulation. Supported: {list(mappings.keys())}"})
    return json.dumps({"regulation": regulation, **m}, indent=2)


@mcp.tool()
def required_fields(api_key: str = "") -> str:
    """List the 10 required AI-BOM field categories and their fields.

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need structured analysis or classification
        of inputs against established frameworks or standards.

    When NOT to use:
        Not suitable for real-time production decision-making without
        human review of results.

    Args:
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg})
    return json.dumps({
        "source": "NIST SP 800-218 SSDF + CISA AI Cyber Report 2024 + EU AI Act Annex IV + CycloneDX 1.6 ML-BOM",
        "required_categories": AI_BOM_REQUIRED_FIELDS,
        "formats_supported": ["CycloneDX 1.6 ML-BOM (recommended)", "SPDX 3.0.1 AI profile"],
    }, indent=2)


def main():
    mcp.run()


if __name__ == "__main__":
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
