"""SOVOS Dream Engine - a pluggable orchestration backend for the OOWM.

'Dream depth on demand': a governance-critical decision can use a deep
frontier dream engine (e.g. Nemotron 3 Ultra), while routine actions use a
fast local engine. This module is a thin, dependency-light client so the
core SOVOS evaluator can *consume* an OOWM's judgment and stamp it with a
GSPC score - without hard-wiring SOVOS to any single endpoint.

NOTE: No API key is required to import or use the governance layer. The
remote client activates only when an OpenRouter key is supplied. Spending
credits remains owner-gated.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from .gspc import score_gspc


@dataclass
class DreamResult:
    """The outcome of a 'dream' - an OOWM judgment plus its governance stamp."""

    engine: str
    raw_response: str
    reasoning: str
    depth: str
    gspc: dict


class NemotronClient:
    """Minimal OpenRouter client for Nemotron 3 Ultra (deep dream engine).

    Hard limits (OpenRouter free tier): 50 req/day free, 1000 req/day after
    buying $10 credits, 20 req/min. Never hard-wire a recurring mission to a
    :free endpoint - hence the local fallback contract below.
    """

    BASE = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "nvidia/nemotron-3-ultra"

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model = model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def dream(
        self,
        prompt: str,
        enable_thinking: bool = True,
        max_tokens: int = 512,
        timeout: float = 60.0,
    ) -> DreamResult:
        """Run a deep-dream consult. Raises if no key configured."""
        if not self.available:
            raise RuntimeError(
                "No OpenRouter API key set. Set OPENROUTER_API_KEY or pass api_key. "
                "This is one of 50 free req/day (1000 after $10 credits)."
            )
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "enable_thinking": enable_thinking,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            self.BASE,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://csoai.org",
                "X-Title": "SOVOS",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"].get("content", "")
        reasoning = data["choices"][0]["message"].get("reasoning", "")
        # Stamp the dream's own governance record (best-effort, deterministic).
        gspc = score_gspc({"reasoning": reasoning, "raw_response": content}).report()
        return DreamResult(
            engine=self.model,
            raw_response=content,
            reasoning=reasoning,
            depth="deep" if enable_thinking else "shallow",
            gspc=gspc,
        )


class LocalFallback:
    """Local-fast dream engine contract (e.g. Gemma 4 / SOV3).

    Keep SOVOS resilient: if the frontier free tier vanishes, this interface
    is satisfied by a local endpoint. Governance stamping is engine-agnostic.
    """

    def __init__(self, engine_name: str = "local-fast"):
        self.engine_name = engine_name

    def dream(self, prompt: str, enable_thinking: bool = False, **_) -> DreamResult:
        # Replace with a real local-inference call (TurboFieldfare / Ollama).
        content = f"[{self.engine_name}] (placeholder response) :: {prompt[:120]}"
        gspc = score_gspc({"raw_response": content}).report()
        return DreamResult(
            engine=self.engine_name,
            raw_response=content,
            reasoning="",
            depth="shallow",
            gspc=gspc,
        )


def governed_dream(engine, prompt: str, enable_thinking: bool = True) -> DreamResult:
    """Dream through any engine and return the GSPC-stamped result (e2e)."""
    return engine.dream(prompt=prompt, enable_thinking=enable_thinking)
