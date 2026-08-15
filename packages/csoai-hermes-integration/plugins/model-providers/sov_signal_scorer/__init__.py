"""sov_signal_scorer — Expose SOV Signal scoring as a Hermes model provider.

Hermes model providers are Python objects that implement a small interface
(openai-compatible). We implement one that, given a chat prompt, calls the
SOV Signal API and returns the 4-axis GSPC score as a JSON string.

This is the same `register` pattern the langfuse plugin uses.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import httpx  # type: ignore
    _HTTPX_AVAILABLE = True
except Exception:  # pragma: no cover
    httpx = None
    _HTTPX_AVAILABLE = False


PROVIDER_NAME = "sov_signal_scorer"


def _api_url() -> str:
    return os.environ.get("SOV_SIGNAL_API_URL", "https://signal.csoai.org").rstrip("/")


def _api_key() -> Optional[str]:
    return os.environ.get("SOV_SIGNAL_API_KEY")


class SovSignalScorer:
    """Model provider that scores text on the 4 GSPC axes.

    The model name is `sov_signal_scorer` and the response is a JSON string:
    `{"G": 0.xx, "S": 0.xx, "P": 0.xx, "C": 0.xx}` plus an `ed25519_signature`.

    If the API is unreachable, returns a deterministic local heuristic so
    the provider is never silently no-op.
    """

    name = PROVIDER_NAME

    def __init__(self) -> None:
        self.api_url = _api_url()
        self.api_key = _api_key()

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> Dict[str, Any]:
        user = messages[-1]["content"] if messages else ""
        if self.api_key and _HTTPX_AVAILABLE:
            try:
                r = httpx.post(
                    f"{self.api_url}/v1/score",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"text": user[:4000]},
                    timeout=3.0,
                )
                if r.status_code == 200:
                    return {"role": "assistant", "content": r.text}
            except Exception as e:  # pragma: no cover
                logger.debug(f"SOV Signal API unreachable ({e}); using local heuristic")
        # Local fallback (deterministic)
        score = _local_score(user)
        return {"role": "assistant", "content": json.dumps(score, indent=2)}


def _local_score(text: str) -> Dict[str, float]:
    """Same deterministic heuristic as sov_governance (last-resort fallback)."""
    t = text.lower().strip()
    if not t:
        return {"G": 0.0, "S": 0.0, "P": 0.0, "C": 0.0}
    gov_keys = ("eu ai act", "annex iii", "article 5", "gdpr", "data minimis", "nist rmf")
    gov = min(sum(0.20 for k in gov_keys if k in t), 1.0)
    safety = 0.85 if any(s in t for s in ("i can't", "i cannot", "sorry")) else 0.55
    provenance = 0.75 if len(t) < 800 else 0.45
    care = 0.80 if any(s in t for s in ("human", "user", "harm", "impact", "people")) else 0.50
    return {"G": round(gov, 4), "S": round(safety, 4), "P": round(provenance, 4), "C": round(care, 4)}


# ---------------------------------------------------------------------------
# Hermes plugin registration
# ---------------------------------------------------------------------------
def register(plugin_manager: Any) -> None:
    """Register this provider with Hermes's model-provider registry."""
    provider = SovSignalScorer()
    if hasattr(plugin_manager, "register_model_provider"):
        plugin_manager.register_model_provider(PROVIDER_NAME, provider)
        logger.info(f"SOV signal scorer registered as model provider: {PROVIDER_NAME}")
    else:
        logger.warning("plugin_manager has no register_model_provider; nothing to do")