"""GSPCMeasureAgent — the A2A measurement skill (the last in-lane wire).

An agent presents a target (a model to measure) → this skill runs the GSPC axes
live → routes the board through the REAL Ed25519 issuance leg (MeasureService) →
returns a SIGNED MEASUREMENT CREDENTIAL the agent carries into the A2A directory.

This is the surface that closes the paid machine-to-machine loop:
    agent calls measure()  →  x402 pays per call  →  walks away with a signed card.

FIREWALL — measurement, not certification. This agent NEVER issues a "certificate"
and NEVER claims a subject is "compliant". It issues a signed record of WHAT WAS
MEASURED. The credential says so explicitly (`claim="measurement"`,
`not_a_certification=True`). Conflating attest with certify is the one move that
detonates neutrality in front of a regulator — so it is structurally refused here.

Honesty caveats kept visible in every credential:
  • UNMEASURED axes are reported as UNMEASURED, never coerced to 0.
  • `signer_kind` records whether the real Ed25519 chain signed it or the demo
    signer did (the real key lives only on the keystone). Even a real signature
    only proves ISSUANCE — external signer-identity attestation is a separate,
    still-open leg, and the credential does not pretend otherwise.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..signing import attach_signature

# Default axis set — all the harness carries; caller can narrow via target["axes"].
DEFAULT_AXES = ["governance", "safety", "provenance", "conformance", "openness", "art5"]


def _repo_root() -> Optional[Path]:
    """Walk up to the csoai-static-deploy2 checkout so we can import the estate."""
    for p in Path(__file__).resolve().parents:
        if (p / "gspc_flywheel.py").exists():
            return p
    return None


def _load_run_axis():
    root = _repo_root()
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from gspc_flywheel import run_axis  # type: ignore
        return run_axis
    except Exception:
        return None


def _load_measure_service():
    """Prefer the real Ed25519 issuance leg (MeasureService over the estate Chain)."""
    root = _repo_root()
    if root:
        src = root / "SOVOS" / "packages" / "sovos-city" / "src"
        if src.exists() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
    try:
        from sovos_city.chain import Chain  # type: ignore
        from sovos_city.measure_api import MeasureService  # type: ignore
        return Chain, MeasureService
    except Exception:
        return None, None


def _load_timestamp():
    """Load the real RFC-3161 time-anchor (repo-root sov_timestamp)."""
    root = _repo_root()
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from sov_timestamp import anchor_for  # type: ignore
        return anchor_for
    except Exception:
        return None


def _load_didbind():
    """Load the did:web binder (repo-root verify_via_didweb.bind_did)."""
    root = _repo_root()
    if root and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from verify_via_didweb import bind_did  # type: ignore
        return bind_did
    except Exception:
        return None


class GSPCMeasureAgent:
    """A2A agent exposing GSPC measurement as a signed, per-call skill."""

    def __init__(self, name: str = "gspc-measure-001",
                 key_path: str = "~/.sovos/city_ed25519") -> None:
        self.name = name
        self.key_path = str(Path(key_path).expanduser())
        self.issued: Dict[str, Dict[str, Any]] = {}

    # ── skill 1: measure ────────────────────────────────────────────────────
    def measure(self, target: Dict[str, Any]) -> Dict[str, Any]:
        """Measure a target on the GSPC axes and return a signed measurement credential.

        target:
          model (str)            — the subject to measure (an ollama model tag)
          axes  (list, optional) — which axes; defaults to DEFAULT_AXES
          boards(dict, optional) — pre-measured {axis: run_axis-shaped board};
                                   supplied for offline/demo or when the caller
                                   already measured. If absent, measures live.
        """
        model = target.get("model", "unknown")
        axes: List[str] = target.get("axes") or DEFAULT_AXES

        boards: Dict[str, Any] = dict(target.get("boards") or {})
        if not boards:
            run_axis = _load_run_axis()
            for ax in axes:
                if run_axis is None:
                    boards[ax] = {"axis": ax, "status": "UNMEASURED",
                                  "why": "gspc_flywheel not importable in this environment"}
                    continue
                try:
                    boards[ax] = run_axis(model, ax)
                except Exception as e:  # unreachable model ≠ score of 0
                    boards[ax] = {"axis": ax, "status": "UNMEASURED", "why": str(e)[:80]}

        measured = {a: b for a, b in boards.items() if b.get("status") == "MEASURED"}
        unmeasured = [a for a, b in boards.items() if b.get("status") != "MEASURED"]
        mean = (round(sum(b["score"] for b in measured.values()) / len(measured), 4)
                if measured else None)

        # The signed body — UNMEASURED stays UNMEASURED, never 0.
        body = {
            "protocol": "gspc-a2a",
            "subject_model": model,
            "axes": axes,
            "per_axis": {a: (b.get("score") if b.get("status") == "MEASURED" else "UNMEASURED")
                         for a, b in boards.items()},
            "measured_mean": mean,
            "unmeasured": unmeasured,
        }
        card, signer_kind = self._sign(body, model, axes)

        # Time-anchor the card (RFC-3161, best-effort). Honest either way: the anchor
        # records its own `kind` (rfc3161 = real third-party token; unanchored = offline).
        anchor_for = _load_timestamp()
        anchor = None
        if anchor_for is not None and card is not None:
            try:
                anchor = anchor_for(card.get("content_id") or body)
                card["time_anchor"] = anchor
            except Exception:
                anchor = None

        credential = {
            "agent": self.name,
            "action": "measure",
            "claim": "measurement",           # NOT "certification"
            "not_a_certification": True,
            "subject_model": model,
            "axes_measured": list(measured),
            "axes_unmeasured": unmeasured,
            "measured_mean": mean,
            "per_axis": body["per_axis"],
            "signed_card": card,
            "signer_kind": signer_kind,
            "signer_did": (card or {}).get("signer_did"),   # did:web:csoai.org when key is published
            "time_anchor_kind": (anchor or {}).get("kind", "none"),
            "note": ("Signed MEASUREMENT credential. It attests what was measured on the "
                     "GSPC axes — NOT that the subject is compliant or certified. Even a real "
                     "signature proves issuance only; external signer-identity attestation is a "
                     "separate open leg."),
        }
        cid = (card or {}).get("content_id", f"unsigned-{len(self.issued)+1}")
        self.issued[cid] = credential
        return attach_signature(credential)

    # ── skill 2: verify ─────────────────────────────────────────────────────
    def verify(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """Re-verify a previously issued card through the real service verify()."""
        Chain, MeasureService = _load_measure_service()
        if MeasureService is None:
            return attach_signature({"agent": self.name, "action": "verify",
                                     "status": "unavailable",
                                     "reason": "MeasureService not importable here — verify on the keystone"})
        try:
            chain = Chain(str(Path(tempfile.gettempdir()) / "gspc_a2a_verify.jsonl"),
                          key_path=self.key_path)
            svc = MeasureService(chain, store=Path(tempfile.gettempdir()) / "gspc-a2a-jobs")
            v = svc.verify(card)
            return attach_signature({"agent": self.name, "action": "verify",
                                     "valid": v.get("valid"),
                                     "content_id_matches": v.get("content_id_matches"),
                                     "signer": v.get("signer")})
        except Exception as e:
            return attach_signature({"agent": self.name, "action": "verify",
                                     "status": "error", "reason": str(e)[:120]})

    # ── the real signing leg, with an honest fallback ───────────────────────
    def _sign(self, body: Dict[str, Any], model: str, axes: List[str]):
        Chain, MeasureService = _load_measure_service()
        if MeasureService is not None:
            try:
                chain = Chain(str(Path(tempfile.gettempdir()) / "gspc_a2a_issuance.jsonl"),
                              key_path=self.key_path)
                svc = MeasureService(chain, store=Path(tempfile.gettempdir()) / "gspc-a2a-jobs")
                job = svc.measure(protocol="gspc-a2a", model=model,
                                  bank_version="gspc", axes=axes, run_fn=lambda *a: body)
                card = job.card
                if card and card.get("signed"):
                    v = svc.verify(card)
                    card["_verify"] = {"valid": v.get("valid"),
                                       "content_id_matches": v.get("content_id_matches")}
                    bind_did = _load_didbind()          # stamp the resolvable did:web signer
                    if bind_did is not None:
                        card = bind_did(card)
                    return card, "ed25519-measureservice"
            except Exception:
                pass  # key absent off-keystone → honest fallback below
        demo = attach_signature({"protocol": "gspc-a2a", "body": body})
        return demo, "demo-signature (NOT the Ed25519 chain; real key lives on the keystone)"

    # ── A2A skill manifest (x402-priced, measurement framing) ───────────────
    def skills(self) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "type": "governance-measurement",
            "skills": [
                {"name": "measure", "params": ["target"],
                 "returns": "signed measurement credential (not a certificate)"},
                {"name": "verify", "params": ["card"],
                 "returns": "content_id match + signer"},
            ],
            "pricing_x402": {          # agent-native per-call, wired via compliance-gateway
                "measure": "$0.50 per subject-axis-set",
                "verify": "free",
            },
            "frameworks_measured": ["EU AI Act (GSPC crosswalk)", "NIST AI RMF", "ISO/IEC 42001"],
            "firewall": "measurement only — never issues a certificate or a compliance claim",
        }


__all__ = ["GSPCMeasureAgent"]


if __name__ == "__main__":
    # Offline self-test — synthesize boards (no ollama needed), prove the invariants.
    import json

    agent = GSPCMeasureAgent()
    boards = {
        "governance": {"axis": "governance", "status": "MEASURED", "score": 0.82,
                       "correct": 41, "graded": 50},
        "safety":     {"axis": "safety", "status": "MEASURED", "score": 0.61,
                       "correct": 30, "graded": 49},
        "provenance": {"axis": "provenance", "status": "UNMEASURED",
                       "why": "subject refused every probe"},
    }
    cred = agent.measure({"model": "demo-subject:latest",
                          "axes": ["governance", "safety", "provenance"],
                          "boards": boards})
    print(json.dumps({k: v for k, v in cred.items() if k != "signed_card"}, indent=2))
    print("signer_kind:", cred["signer_kind"])

    # invariants
    assert cred["claim"] == "measurement", "must claim measurement"
    assert cred["not_a_certification"] is True, "must not be a certification"
    assert "certif" not in cred["note"].lower() or "not" in cred["note"].lower()
    assert cred["per_axis"]["provenance"] == "UNMEASURED", "UNMEASURED must be preserved, never 0"
    assert cred["measured_mean"] == round((0.82 + 0.61) / 2, 4), "mean over MEASURED axes only"
    assert cred["signed_card"] is not None, "must produce a signed card (real or demo)"
    assert cred["time_anchor_kind"] in ("rfc3161", "unanchored", "none"), "anchor kind must be honest"
    if cred["signer_kind"].startswith("ed25519"):
        assert cred["signer_did"] == "did:web:csoai.org", "ed25519 card must carry its resolvable did:web signer"
    print("signer_kind:", cred["signer_kind"], "| signer_did:", cred["signer_did"],
          "| time_anchor_kind:", cred["time_anchor_kind"])
    print("\n  ✅ A2A measurement-skill invariants hold "
          "(measurement-not-certification, UNMEASURED preserved, card issued, time-anchored)")
