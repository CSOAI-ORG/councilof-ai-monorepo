#!/usr/bin/env python3
"""B-Space — Browser Space Runtime for SOV-Space

B-Space is where all agentic work happens. It's the "hands" of SOV.
Every browser action is recorded, sigiled, and visually mapped.

Architecture:
  Browser Pool (Playwright instances)
  Action Recorder (every click/type sigiled)
  Visual Mapper (screenshots, DOM diffs, action graphs)
  Agent Workspace (isolated per-agent browser context)
  Memory Store (what agents saw, did, learned)

All12 OWEM families can spawn agents that work inside B-Space.
End user can see everything or just J-space.
"""

import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

ROOT = Path(__file__).resolve().parent.parent
SOV_SPACE = ROOT / "benchmark-results" / "sov-space"
B_SPACE = ROOT / "b_space"
B_SPACE.mkdir(parents=True, exist_ok=True)


# ─── Action Types ────────────────────────────────────────────────────────────

ACTION_TYPES = {
    "navigate": {"sigil_type": "b_space.navigate", "care_floor": 0.95},
    "click": {"sigil_type": "b_space.click", "care_floor": 0.95},
    "type": {"sigil_type": "b_space.type", "care_floor": 0.95},
    "screenshot": {"sigil_type": "b_space.screenshot", "care_floor": 0.95},
    "evaluate": {"sigil_type": "b_space.evaluate", "care_floor": 0.95},
    "wait": {"sigil_type": "b_space.wait", "care_floor": 0.95},
    "scroll": {"sigil_type": "b_space.scroll", "care_floor": 0.95},
    "submit": {"sigil_type": "b_space.submit", "care_floor": 0.95},
}


class BSpaceAction:
    """A single browser action — recorded with sigil chain."""

    def __init__(self, action_type: str, target: str = "", value: str = "",
                 agent_id: str = "", pillar: str = ""):
        self.action_type = action_type
        self.target = target
        self.value = value
        self.agent_id = agent_id
        self.pillar = pillar
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.sigil = None

    def to_dict(self) -> Dict:
        return {
            "type": self.action_type,
            "target": self.target,
            "value": self.value,
            "agent_id": self.agent_id,
            "pillar": self.pillar,
            "timestamp": self.timestamp,
            "sigil": self.sigil,
        }


class BSpaceContext:
    """An isolated browser context for an agent."""

    def __init__(self, agent_id: str, pillar: str):
        self.agent_id = agent_id
        self.pillar = pillar
        self.actions: List[BSpaceAction] = []
        self.screenshots: List[bytes] = []
        self.dom_snapshots: List[str] = []
        self.created_at = datetime.now(timezone.utc).isoformat()

    def record_action(self, action: BSpaceAction):
        """Record an action with sigil."""
        action.sigil = self._generate_sigil(action)
        self.actions.append(action)
        return action.sigil

    def _generate_sigil(self, action: BSpaceAction) -> Dict:
        """Generate a sigil for this action."""
        payload = {
            "type": action.action_type,
            "target": action.target,
            "value": action.value,
            "agent_id": self.agent_id,
            "pillar": self.pillar,
            "timestamp": action.timestamp,
        }
        payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        prev_hash = self.actions[-1].sigil["payload_hash"] if self.actions else "0" * 64
        root_hash = hashlib.sha256((prev_hash + payload_hash).encode()).hexdigest()

        return {
            "payload_hash": payload_hash,
            "prev_hash": prev_hash,
            "root_hash": root_hash,
            "agent_did": f"did:csoai:{self.agent_id}",
            "timestamp": action.timestamp,
        }

    def get_action_timeline(self) -> List[Dict]:
        """Get the action timeline for visualization."""
        return [a.to_dict() for a in self.actions]


class BSpaceRuntime:
    """The B-Space runtime — manages browser contexts and agent work."""

    def __init__(self):
        self.contexts: Dict[str, BSpaceContext] = {}
        self.active_agents: Dict[str, str] = {}  # agent_id -> context_id
        self.action_count = 0
        self.sigil_chain_head = "0" * 64

    def spawn_agent(self, agent_id: str, pillar: str) -> BSpaceContext:
        """Spawn an agent in B-Space."""
        context = BSpaceContext(agent_id, pillar)
        self.contexts[agent_id] = context
        self.active_agents[agent_id] = agent_id
        return context

    def dispatch_action(self, agent_id: str, action_type: str,
                        target: str = "", value: str = "") -> Dict:
        """Dispatch an action for an agent."""
        if agent_id not in self.contexts:
            return {"error": f"Agent {agent_id} not found in B-Space"}

        context = self.contexts[agent_id]
        action = BSpaceAction(
            action_type=action_type,
            target=target,
            value=value,
            agent_id=agent_id,
            pillar=context.pillar,
        )

        sigil = context.record_action(action)
        self.action_count += 1
        self.sigil_chain_head = sigil["root_hash"]

        return {
            "action": action.to_dict(),
            "sigil": sigil,
            "action_count": self.action_count,
        }

    def get_state(self) -> Dict:
        """Get the current B-Space state."""
        return {
            "active_agents": len(self.active_agents),
            "total_contexts": len(self.contexts),
            "total_actions": self.action_count,
            "sigil_chain_head": self.sigil_chain_head,
            "agents": {
                agent_id: {
                    "pillar": ctx.pillar,
                    "actions": len(ctx.actions),
                    "created_at": ctx.created_at,
                }
                for agent_id, ctx in self.contexts.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_visual_map(self, agent_id: str = None) -> Dict:
        """Get visual map of B-Space actions."""
        if agent_id and agent_id in self.contexts:
            context = self.contexts[agent_id]
            return {
                "agent_id": agent_id,
                "timeline": context.get_action_timeline(),
                "action_count": len(context.actions),
            }

        # All agents
        return {
            "total_actions": self.action_count,
            "agents": {
                agent_id: {
                    "timeline": ctx.get_action_timeline(),
                    "action_count": len(ctx.actions),
                }
                for agent_id, ctx in self.contexts.items()
            },
        }


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  B-SPACE — Browser Space Runtime                       ║")
    print("║  Where all agentic work happens inside SOV-space       ║")
    print("╚══════════════════════════════════════════════════════════╝")

    runtime = BSpaceRuntime()

    # Spawn agents from different families
    agents = [
        ("agent-honor", "honor"),
        ("agent-safety", "safety"),
        ("agent-guidance", "guidance"),
        ("agent-auditability", "auditability"),
    ]

    print(f"\n─── SPAWNING AGENTS ───")
    for agent_id, pillar in agents:
        ctx = runtime.spawn_agent(agent_id, pillar)
        print(f"  ✦ {agent_id:25s} pillar={pillar}")

    # Simulate actions
    print(f"\n─── DISPATCHING ACTIONS ───")
    actions = [
        ("agent-honor", "navigate", "https://example.com", ""),
        ("agent-honor", "screenshot", "", ""),
        ("agent-safety", "click", "#login-button", ""),
        ("agent-safety", "type", "#email", "user@example.com"),
        ("agent-guidance", "submit", "#login-form", ""),
        ("agent-auditability", "screenshot", "", ""),
    ]

    for agent_id, action_type, target, value in actions:
        result = runtime.dispatch_action(agent_id, action_type, target, value)
        sigil = result["sigil"]
        print(f"  {agent_id:25s} {action_type:12s} {target:20s} sigil={sigil['payload_hash'][:16]}...")

    # Show state
    state = runtime.get_state()
    print(f"\n─── B-SPACE STATE ───")
    print(f"  Active agents: {state['active_agents']}")
    print(f"  Total contexts: {state['total_contexts']}")
    print(f"  Total actions: {state['total_actions']}")
    print(f"  Sigil chain head: {state['sigil_chain_head'][:16]}...")

    # Show visual map
    visual = runtime.get_visual_map()
    print(f"\n─── VISUAL MAP ───")
    for agent_id, data in visual["agents"].items():
        print(f"  {agent_id:25s} {data['action_count']} actions")
        for action in data["timeline"]:
            print(f"    {action['type']:12s} {action['target']:20s} {action['timestamp'][:19]}")


if __name__ == "__main__":
    main()
