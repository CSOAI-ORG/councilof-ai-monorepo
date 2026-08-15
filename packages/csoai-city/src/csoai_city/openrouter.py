"""OpenRouter citizens — decorrelated bloodlines for the city.

WHY THIS EXISTS, and it is not "more compute".

Every citizen so far has been a local small model: twelve sov6 variants off one
base, plus sov34, gemma3:12b and llama3.2:3b. They are near-clones. The estate
already measured what that costs elsewhere — voting over one shared blob gives
near-zero effective independence — and the city shows the same shape: across
1,300+ turns the population reached for `profile` and `propose_amendment` and
NEVER for `categorise` or `score`, so four of the eight Article 5 subparagraphs
have never been exercised by any citizen.

That is a property of the bloodline, not of the law. Citizens from genuinely
different bases (Anthropic, OpenAI, Google, Meta, Mistral, DeepSeek, Qwen) are
the cheapest available test of whether the 4/8 coverage ceiling is the gate's
narrowness or the population's sameness — a question no amount of extra local
compute can answer.

WHAT THIS DOES NOT TOUCH
    The judge. The gate, the canaries and the paraphrase probes are unchanged and
    still verified against JUDGE.lock. This module only supplies citizens, which
    is generator-side and explicitly free to evolve (Part AV). A frontier citizen
    gets exactly the same brief, the same grammar and the same deterministic
    verdict as a 7B one.

SPEND
    Hard-capped. `Budget` refuses the next call once the projected spend would
    exceed the cap, and the cap is checked BEFORE each request, never after. A
    run reports what it actually spent. There is no "unlimited" setting.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Deliberately one model per lab: the point is decorrelated bases, not a leaderboard.
# Prices are USD per 1M tokens (prompt, completion) as published by OpenRouter; they
# are used ONLY to enforce the cap, and the cap is deliberately conservative.
@dataclass(frozen=True)
class ORModel:
    slug: str
    lab: str
    usd_in: float
    usd_out: float


DECORRELATED_FLEET: List[ORModel] = [
    ORModel("anthropic/claude-3.5-sonnet",       "Anthropic", 3.00, 15.00),
    ORModel("openai/gpt-4o-mini",                "OpenAI",    0.15,  0.60),
    ORModel("google/gemini-flash-1.5",           "Google",    0.075, 0.30),
    ORModel("meta-llama/llama-3.1-70b-instruct", "Meta",      0.30,  0.40),
    ORModel("mistralai/mistral-large",           "Mistral",   2.00,  6.00),
    ORModel("deepseek/deepseek-chat",            "DeepSeek",  0.14,  0.28),
    ORModel("qwen/qwen-2.5-72b-instruct",        "Qwen",      0.35,  0.40),
]

# The cheap subset — same seven labs' small models where available. A 400-turn run
# on these costs cents, so the coverage question can be answered before spending.
CHEAP_FLEET: List[ORModel] = [
    ORModel("openai/gpt-4o-mini",                "OpenAI",    0.15, 0.60),
    ORModel("google/gemini-flash-1.5",           "Google",    0.075, 0.30),
    ORModel("meta-llama/llama-3.1-8b-instruct",  "Meta",      0.055, 0.055),
    ORModel("deepseek/deepseek-chat",            "DeepSeek",  0.14, 0.28),
    ORModel("mistralai/mistral-7b-instruct",     "Mistral",   0.03, 0.055),
]

BY_SLUG = {m.slug: m for m in DECORRELATED_FLEET + CHEAP_FLEET}


def load_key(explicit: Optional[str] = None) -> Optional[str]:
    """Key from arg, env, ~/.openrouter/api_key, or a KEY=VALUE line in ~/.env."""
    if explicit:
        return explicit.strip()
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"].strip()
    p = Path.home() / ".openrouter" / "api_key"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    env = Path.home() / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "OPENROUTER" in line.upper() and "=" in line:
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return v
    return None


@dataclass
class Budget:
    """A hard spend cap, checked BEFORE each call rather than after.

    `exhausted()` is the only gate. There is no override and no unlimited mode:
    a runaway spend on someone else's money is not a failure mode worth leaving
    open for convenience.
    """
    cap_usd: float
    spent_usd: float = 0.0
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    # refuse to start a call whose worst case would breach the cap
    reserve_usd: float = 0.05

    def exhausted(self) -> bool:
        return self.spent_usd + self.reserve_usd >= self.cap_usd

    def charge(self, model: str, t_in: int, t_out: int) -> None:
        m = BY_SLUG.get(model)
        if m:
            self.spent_usd += (t_in / 1e6) * m.usd_in + (t_out / 1e6) * m.usd_out
        self.calls += 1
        self.tokens_in += t_in
        self.tokens_out += t_out

    def report(self) -> Dict[str, Any]:
        return {
            "cap_usd": round(self.cap_usd, 4),
            "spent_usd": round(self.spent_usd, 4),
            "remaining_usd": round(max(0.0, self.cap_usd - self.spent_usd), 4),
            "calls": self.calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "note": ("cap enforced before each call; a run that hits the cap stops asking and "
                     "reports how many turns it never made, rather than truncating silently"),
        }


def ask_openrouter(model: str, prompt: str, key: str, budget: Budget,
                   fmt: Optional[Dict[str, Any]] = None, timeout: float = 120.0,
                   attempts: int = 3) -> Tuple[str, Optional[str], int]:
    """Same contract as arena.ask(): returns (text, error, tries).

    Structured output is requested via response_format json_schema where the model
    supports it. When a model ignores it the answer simply fails to parse and is
    recorded UNMEASURED against that citizen — exactly as for a local model. We do
    not retry into a different format to manufacture a parse.
    """
    if budget.exhausted():
        return "", f"BUDGET: cap ${budget.cap_usd:.2f} reached before this turn", 0

    body: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 600,
    }
    if fmt is not None:
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "city_action", "strict": True, "schema": fmt},
        }

    last = "not attempted"
    for i in range(max(1, attempts)):
        if budget.exhausted():
            return "", f"BUDGET: cap ${budget.cap_usd:.2f} reached mid-retry", i
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://councilof.ai",
                "X-Title": "SOV City - governed multi-agent arena",  # ASCII only: HTTP headers are latin-1
            })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            usage = data.get("usage") or {}
            budget.charge(model, int(usage.get("prompt_tokens", 0)),
                          int(usage.get("completion_tokens", 0)))
            txt = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
            if txt.strip():
                return txt, None, i + 1
            last = "empty response from model"
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:160]
            last = f"HTTP {e.code}: {detail}"
            if e.code in (400, 401, 402, 403):
                return "", f"TRANSPORT: {last}", i + 1  # not retryable
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        if i + 1 < attempts:
            time.sleep(1.5 * (i + 1))

    tag = "MODEL_SILENT" if last == "empty response from model" else "TRANSPORT"
    return "", f"{tag}: {last} (after {attempts} attempts)", attempts


def estimate_run_usd(models: List[str], turns: int,
                     tokens_in: int = 420, tokens_out: int = 260) -> float:
    """Rough cost of a run, so a cap can be chosen with eyes open.

    Token figures are measured averages from the local runs (the brief plus the
    grammar is ~420 in; a structured action is ~260 out). Estimate only — the cap,
    not this number, is what actually stops the spend.
    """
    if not models:
        return 0.0
    per = turns / len(models)
    total = 0.0
    for slug in models:
        m = BY_SLUG.get(slug)
        if m:
            total += per * ((tokens_in / 1e6) * m.usd_in + (tokens_out / 1e6) * m.usd_out)
    return total
