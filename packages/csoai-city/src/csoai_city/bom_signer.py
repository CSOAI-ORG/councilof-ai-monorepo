"""csoai-city.bom_signer — wire the AI-BOM into the estate's SIGNED spine.

Catapult items #20 + #15: the ai-bom-mcp server generates a CycloneDX-style
AI-BOM, but its "sign" hook is a Stripe upsell string, not cryptographic
signing. This module is the honest bridge: take an AI-BOM structure, push it
through the correctness gate (so a signed-but-wrong bare legal assertion can
never be wrapped), and wrap the surviving BOM in the estate's Ed25519
csoai-cose-sign1 envelope. The result is a SIGNED, externally-verifiable
artifact a third party can check with cose_wrapper.verify() — no secret
required, no upsell.

Measurement, not certification. A BOM can be complete AND wrong; the gate is
what stops a signed artifact from carrying an ungrounded legal claim that
would detonate neutrality in front of a regulator.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from . import correctness_gate
from . import cose_wrapper
from .cose_wrapper import canonical

# Estate default signing key — same path the rest of the spine uses. On pods
# where the path is unwritable, pass an explicit writable key_path.
from .keystone import DEFAULT_KEY_PATH as DEFAULT_KEY  # ONE canonical key path (ADR_ONE_SIGNER)

# Deterministic, closed CycloneDX ML-BOM-ish schema identifiers.
BOM_FORMAT = "CycloneDX"
DEFAULT_SPEC_VERSION = "1.7"

# Structural labels (property names, bom-refs, serials, version tags, model
# slugs) are schema identifiers, NOT legal claims. A bare token with no
# whitespace that matches this grammar is treated as a label and skipped by
# the gate; genuine claims are prose (they carry spaces). This is the honest
# line between "a field named aibom:compliance_note" and "the model IS
# compliant" — only the latter is an assertion that must be grounded.
_IDENT_RE = re.compile(r"^[A-Za-z0-9_:\-\./]+$")


def _is_structural_label(s: object) -> bool:
    return isinstance(s, str) and " " not in s and bool(_IDENT_RE.match(s))


def _iter_strings(obj: Any):
    """Yield every leaf string that could carry a legal/regulatory claim.
    Structural labels (no-whitespace identifiers like property names, bom-refs,
    serials) are skipped — they are schema, not assertions."""
    if isinstance(obj, str):
        if not _is_structural_label(obj):
            yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def _first_ungrounded(bom: Dict[str, Any]):
    """Scan the whole BOM; return (claim, verdict) for the first string that
    the correctness gate classifies as an UNGROUNDED legal assertion."""
    for s in _iter_strings(bom):
        verdict = correctness_gate.evaluate(s)
        if verdict.state == "UNGROUNDED":
            return s, verdict
    return None, None


def _bom_serial(model_ref: str, components: List[Any],
                licenses: Dict[str, Any], safety_evals: Dict[str, Any],
                gspc_axes: Optional[Dict[str, float]]) -> str:
    """Deterministic urn:uuid serial number — same inputs -> same serial, so
    the whole BOM (including its id) is reproducible."""
    seed = canonical({
        "model_ref": model_ref,
        "components": components,
        "licenses": licenses,
        "safety_evals": safety_evals,
        "gspc_axes": gspc_axes,
    })
    h = hashlib.sha256(seed).hexdigest()
    return (f"urn:uuid:{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}")


def build_minimal_bom(
    model_ref: str,
    components: List[Any],
    licenses: Dict[str, Any],
    safety_evals: Dict[str, Any],
    gspc_axes: Optional[Dict[str, float]] = None,
    spec_version: str = DEFAULT_SPEC_VERSION,
) -> Dict[str, Any]:
    """Build a minimal, deterministic CycloneDX-style ML-BOM.

    components: list of dependency components, each a dict with at least
                {"name": str} plus optional "version" / "type".
    licenses:  mapping component-name -> list of SPDX ids applied to that
               component, e.g. {"my-model": ["Apache-2.0"]}.
    safety_evals: mapping eval-name -> scalar/result; emitted as
                  aibom:safety:* properties.
    gspc_axes: optional mapping axis -> score; emitted as gspc:* properties.

    Deterministic: no wall-clock timestamp, serialNumber is content-derived.
    """
    def _licenses_for(name: str) -> List[Dict[str, Any]]:
        return [{"license": {"id": lid}} for lid in licenses.get(name, [])]

    # The model itself is always the first component (CycloneDX ML-BOM shape).
    model_component = {
        "type": "model",
        "name": model_ref,
        "version": "unknown",
        "licenses": _licenses_for(model_ref),
    }

    built_components = [model_component]
    for c in components:
        entry: Dict[str, Any] = {
            "type": c.get("type", "component"),
            "name": c["name"],
        }
        if c.get("version"):
            entry["version"] = c["version"]
        lic = _licenses_for(c.get("name"))
        if lic:
            entry["licenses"] = lic
        built_components.append(entry)

    props: List[Dict[str, str]] = []
    for k, v in (safety_evals or {}).items():
        props.append({"name": f"aibom:safety:{k}", "value": str(v)})
    for axis, score in (gspc_axes or {}).items():
        props.append({"name": f"gspc:{axis}", "value": str(score)})

    serial = _bom_serial(model_ref, components, licenses, safety_evals, gspc_axes)

    return {
        "bomFormat": BOM_FORMAT,
        "specVersion": spec_version,
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "component": {
                "bom-ref": f"urn:meok:aibom:{model_ref}",
                "type": "model",
                "name": model_ref,
                "version": "unknown",
                "licenses": _licenses_for(model_ref),
            },
        },
        "components": built_components,
        "properties": props,
    }


def sign_bom(bom: Dict[str, Any], key_path: Optional[str] = None) -> Dict[str, Any]:
    """Gate an AI-BOM, then wrap it in the estate's signed Ed25519 envelope.

    Correctness gate first: if ANY string in the BOM is an assertive legal
    claim with no statutory anchor, refuse to sign (return the refusal) — a
    signed-but-wrong BOM must never leave the estate.

    On success returns: {signed: True, envelope: <dict>, content_id,
                          time_anchor_state, signer_pubkey}
    On gate refusal:     {signed: False, reason: "ungrounded", claim, verdict}
    """
    claim, verdict = _first_ungrounded(bom)
    if claim is not None:
        return {
            "signed": False,
            "reason": "ungrounded",
            "claim": claim,
            "verdict": verdict.to_dict(),
        }

    result = cose_wrapper.wrap(bom, source="ai-bom",
                               key_path=key_path or DEFAULT_KEY)
    if not result.signed:
        return {"signed": False, "reason": "signing_failed", "error": result.error}

    envelope = json.loads(result.envelope)
    return {
        "signed": True,
        "envelope": envelope,
        "content_id": result.content_id,
        "time_anchor_state": result.time_anchor_state,
        "signer_pubkey": envelope.get("signer_pubkey"),
    }


def self_test() -> int:
    ok = fail = 0

    def t(name: str, cond: bool, extra: str = ""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # Use a writable key path so signing actually exercises the spine.
    import tempfile, os
    key_path = os.path.join(tempfile.gettempdir(), "csoai_city_bom_test_ed25519")
    # don't reuse a stale key in a way that breaks anything; wrap regenerates if absent

    # (a) build_minimal_bom produces valid structure with the given components
    bom = build_minimal_bom(
        "cs49ce-ai-advisor",
        components=[{"name": "transformers", "version": "4.46"}, {"name": "tokenizers"}],
        licenses={"cs49ce-ai-advisor": ["Apache-2.0"], "transformers": ["Apache-2.0"]},
        safety_evals={"toxicity": 0.02, "stereotype": 0.01},
        gspc_axes={"gov": 0.81, "care": 0.74},
    )
    t("bomFormat is CycloneDX", bom.get("bomFormat") == "CycloneDX")
    t("components non-empty incl model", len(bom.get("components", [])) >= 2)
    t("serialNumber present + deterministic length",
      isinstance(bom.get("serialNumber"), str) and len(bom["serialNumber"]) == 45)
    t("safety evals in properties",
      any(p["name"] == "aibom:safety:toxicity" for p in bom["properties"]))
    t("gspc axes in properties",
      any(p["name"] == "gspc:gov" for p in bom["properties"]))
    t("component license attached",
      bom["components"][0]["licenses"][0]["license"]["id"] == "Apache-2.0")

    # (d) determinism: same inputs -> same structure
    bom2 = build_minimal_bom(
        "cs49ce-ai-advisor",
        components=[{"name": "transformers", "version": "4.46"}, {"name": "tokenizers"}],
        licenses={"cs49ce-ai-advisor": ["Apache-2.0"], "transformers": ["Apache-2.0"]},
        safety_evals={"toxicity": 0.02, "stereotype": 0.01},
        gspc_axes={"gov": 0.81, "care": 0.74},
    )
    t("deterministic serial", bom["serialNumber"] == bom2["serialNumber"])
    t("deterministic structure", json.dumps(bom, sort_keys=True) == json.dumps(bom2, sort_keys=True))

    # (b) grounded BOM -> signed True + envelope verifies
    grounded_bom = build_minimal_bom(
        "cs49ce-ai-advisor",
        components=[{"name": "transformers", "version": "4.46"}],
        licenses={"cs49ce-ai-advisor": ["Apache-2.0"]},
        safety_evals={},
        gspc_axes={"gov": 0.81},
    )
    # an anchored legal note: cites Article 9 -> GROUNDED, does not block signing
    grounded_bom["properties"].append(
        {"name": "aibom:compliance_note",
         "value": "Demonstrates risk-management alignment with Article 9 of Regulation (EU) 2024/1689"})
    sig = sign_bom(grounded_bom, key_path=key_path)
    t("grounded BOM signs", sig.get("signed") is True, str(sig)[:200])
    if sig.get("signed"):
        v = cose_wrapper.verify(sig["envelope"])
        t("envelope verifies (Ed25519)", v.get("valid") is True, str(v))
        t("content_id sha256", len(sig.get("content_id", "")) == 64)
        t("payload carries the BOM",
          sig["envelope"]["payload"]["data"]["bomFormat"] == "CycloneDX")

    # (c) ungrounded assertive legal claim -> refuse
    ungrounded = build_minimal_bom("cs49ce-ai-advisor", [], {}, {})
    ungrounded["properties"].append(
        {"name": "aibom:compliance_claim",
         "value": "This model is fully compliant with all obligations."})
    ref = sign_bom(ungrounded, key_path=key_path)
    t("ungrounded refused", ref.get("signed") is False, str(ref)[:200])
    t("ungrounded reason", ref.get("reason") == "ungrounded", str(ref)[:200])
    t("ungrounded verdict state",
      ref.get("verdict", {}).get("state") == "UNGROUNDED", str(ref)[:200])

    # an in-band bare legal assertion anywhere in the BOM is also caught
    sneaky = build_minimal_bom("x", [], {}, {})
    sneaky["components"].append({"type": "component", "name": "lib",
                                 "note": "this is definitely compliant."})
    sneaky_sig = sign_bom(sneaky, key_path=key_path)
    t("in-band ungrounded caught", sneaky_sig.get("signed") is False)

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
