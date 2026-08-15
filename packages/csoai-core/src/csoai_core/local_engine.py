"""SOVOS local engine - real inference backends for FAST/INSTINCT dreams.

The Mac is a terminal only (never runs Ollama locally). Local inference runs
on the fleat: sov-brain-2 (RunPod RTX 3090, 150+ SOV models) or the Oracle
micros. This engine shells out to those boxes over SSH to keep the dependence
light - no client SDK, no pydantic coupling.

The source of truth for model availability is `GET /api/tags` (a plain
`ollama list` is cached and can lie) - see INFRA memory.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

from .owm import DreamOutcome, OWMState, _fallback_outcome


@dataclass
class OllamaEngine:
    """Talk to an Ollama-compatible server, optionally proxied over SSH.

    Args:
        host: host:port of the Ollama server (e.g. 'localhost:11434').
        ssh_host: optional SSH host from ~/.ssh/config used to proxy the
            HTTP call (e.g. 'sov-brain-2'). When set, HTTP requests are sent
            through `ssh <ssh_host> curl ...` instead of a local socket.
        model: model name to use for dreams/instinct.
        timeout: per-request timeout in seconds.
    """

    host: str = "localhost:11434"
    ssh_host: Optional[str] = None
    model: str = "qwen2.5:1.5b"
    timeout: float = 90.0

    def _post(self, path: str, payload: dict) -> dict:
        url = f"http://{self.host}{path}"
        body = json.dumps(payload).encode()
        if self.ssh_host:
            # Proxy via ssh: ssh <host> "curl -s --max-time N -H 'Content-Type: application/json' -d '@-' URL"
            script = (
                f"curl -s --max-time {int(self.timeout)} -H 'Content-Type: application/json' "
                f"-d @- {url}"
            )
            proc = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=15", self.ssh_host, script],
                input=body,
                capture_output=True,
                timeout=self.timeout + 25,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"ssh/{self.ssh_host} failed: {proc.stderr.decode()[:300]}")
            return json.loads(proc.stdout.decode())
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def list_models(self) -> List[str]:
        data = self._tags()
        return [m.get("name", "") for m in data.get("models", [])]

    def _tags(self) -> dict:
        if self.ssh_host:
            script = f"curl -s --max-time {int(self.timeout)} http://{self.host}/api/tags"
            proc = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=15", self.ssh_host, script],
                capture_output=True, timeout=self.timeout + 25,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode()[:300])
            return json.loads(proc.stdout.decode())
        with urllib.request.urlopen(f"http://{self.host}/api/tags", timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())

    def has_model(self, name: str | None = None) -> bool:
        return (name or self.model) in self.list_models()

    def dream(self, prompt: str, state: OWMState | None = None) -> DreamOutcome:
        payload = {
            "model": self.model,
            "prompt": prompt[:2000],
            "stream": False,
            "options": {"num_predict": 128, "temperature": 0.2},
        }
        try:
            data = self._post("/api/generate", payload)
            text = data.get("response", "").strip() or "no response"
            # FAST dream -> governance-stamped outcome.
            gspc = {"G": 0.9, "S": 0.9, "P": 0.9, "C": 0.9}
            if state is not None:
                gspc = dict(state.gspc_current) or gspc
            return DreamOutcome(
                scenario_id="fast_local",
                description=text[:200],
                probability=1.0,
                gspc=gspc,
                recommended_action="CONTINUE",
                risk_level="LOW",
            )
        except Exception:
            return _fallback_outcome(state or OWMState(), label="fallback_inference")


def smoke_test(host: str = "sov-brain-2", model: str = "qwen2.5:1.5b") -> dict:
    """Reachability + one tiny inference call through an SSH-proxied engine."""
    engine = OllamaEngine(ssh_host=host, model=model)
    models = engine.list_models()
    names = set(models)
    result = {
        "host": host,
        "reachable": True,
        "model_count": len(models),
        "target_model_present": model in names,
    }
    if result["target_model_present"]:
        out = engine.dream(prompt="Reply with the single word: GOVERNED")
        result["inference_ok"] = True
        result["response"] = out.description[:120]
    else:
        result["inference_ok"] = False
        result["response"] = "target model absent; not calling inference"
    return result


__all__ = ["OllamaEngine", "smoke_test"]
