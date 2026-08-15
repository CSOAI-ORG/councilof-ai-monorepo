#!/usr/bin/env python3
"""arena-mcp — the CSOAI arena as an agent-callable MCP surface.

Exposes the deterministic-battle arena (Bradley-Terry ratings over graded probes —
the open-source Chatbot Arena rating method, our deterministic verdicts) to agents:

  tools:
    arena_leaderboard() -> the current BT leaderboard (real, dated, UNRATED honest)
    arena_method()      -> exactly how a battle is derived and why it's reproducible
    arena_visual()      -> where the human-facing visual lives (CSOAI OS · Arena app)

Standalone scaffold matching the estate's lightweight MCP packages (self-measuring-mcp
pattern): importable tool functions + `python server.py` demo; stdio/HTTP binding is
wired per hosting. Reads the ratings artifact produced by arena_bt.py; if absent it
says so honestly instead of inventing rows.

FIREWALL: a rating is a measurement record, never a certification, endorsement,
or ranking advice. UNRATED models are reported UNRATED — never defaulted.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

REPO = Path(__file__).resolve().parents[4]
RATINGS = REPO / "benchmark-results" / "arena_bt_ratings.json"
VISUAL_URL = "https://csoai.org/os.html"   # CSOAI OS → Arena app (deploy-gated)

TOOLS = {
    "arena_leaderboard": "Current Bradley-Terry leaderboard over deterministic battles (real, dated).",
    "arena_method": "How a battle is derived; why every outcome is a reproducible predicate.",
    "arena_visual": "The human-facing visual surface for this data (CSOAI OS · Arena app).",
}


def arena_leaderboard() -> Dict[str, Any]:
    if not RATINGS.exists():
        return {"available": False,
                "reason": f"ratings artifact not present at {RATINGS.name} — run arena_bt.py; "
                          "this tool never invents rows"}
    d = json.loads(RATINGS.read_text())
    return {"available": True, "claim": "measurement", "not_a_certification": True,
            "battle_pairs": d.get("battle_pairs"), "items_graded": d.get("items_graded"),
            "leaderboard": d.get("leaderboard", [])}


def arena_method() -> Dict[str, Any]:
    return {
        "battle": ("two models answered the SAME frozen probe; the deterministic grader marked "
                   "exactly one correct → one battle. Both-right/both-wrong = no battle (no signal)."),
        "rating": "standard Bradley-Terry MLE, Elo-like scale (1000 + 400·log10 r)",
        "lineage": ("rating method as in the original open-source Chatbot Arena (Apache-2.0); "
                    "the verdicts are CSOAI's deterministic graders — no preference votes"),
        "honesty": ["UNRATED below the battle floor, never a default",
                    "no-signal items dropped, stated",
                    "ratings dated to their board run; drift re-attestation can stale them"],
    }


def arena_visual() -> Dict[str, Any]:
    return {"url": VISUAL_URL, "app": "Arena (dock: ⚔)",
            "note": "deploy-gated — served once the csoai-site Pages deploy runs; "
                    "the page renders this same ratings artifact"}


def main() -> int:   # demo binding
    print(json.dumps({"tools": TOOLS,
                      "leaderboard": arena_leaderboard(),
                      "method": arena_method(),
                      "visual": arena_visual()}, indent=1)[:1200])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
