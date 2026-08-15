"""csoai-a2a-swarm — A2A swarm demo: FishKeeper → MuckAway → CouncilOf.

Three agents that talk to each other using JSON-over-HTTP, demonstrating
the agent-hires-agent pattern from the Aug 2026 brief:

1. **FishKeeper** (koi farm AI) — monitors water quality, alerts on
   ammonia / pH / temperature anomalies.
2. **MuckAway** (waste logistics AI) — plans waste collection routes,
   dispatches hauliers.
3. **CouncilOf** (governance AI) — audits agent decisions against EU
   AI Act / NIST RMF, issues compliance certificates.

Each agent:
- Speaks JSON over HTTP at `/agent/{name}/invoke`
- Has a public skill manifest (`/agent/{name}/skills`)
- Logs every decision (in-memory only; no persistence in v0.1.0)
- Returns a signed (HMAC-SHA256) response with a task vector

This is the **A2A (Agent-to-Agent) layer** from the brief — not the
Google A2A spec, but a minimal honest implementation that proves the
swarm pattern works.

NOT real A2A spec: Google A2A requires JSON-RPC, agent cards, signed
JWT, task lifecycle management. We use plain JSON + HMAC for clarity.
The pattern is the same; the protocol is simplified.
"""
from .agents.fishkeeper import FishKeeperAgent
from .agents.muckaway import MuckAwayAgent
from .agents.councilof import CouncilOfAgent
from .swarm import SwarmOrchestrator, swarm_demo
from .signing import sign_response, verify_response

__all__ = [
    "FishKeeperAgent",
    "MuckAwayAgent",
    "CouncilOfAgent",
    "SwarmOrchestrator",
    "swarm_demo",
    "sign_response",
    "verify_response",
]
