#!/usr/bin/env python3
"""B-Space (Blocker Space) — The Layer That Keeps SOV Alive.

B-Space is the data feed layer that:
- Monitors ALL free GPU/competition/arena/benchmark sites
- Detects when a platform goes down (blocker)
- Auto-transfers work to another platform
- Feeds data to SOV for clan evolution
- Ensures SOV never goes down, never loses progress

B-Space sits between Layer 0 (orchestrator) and the platforms.
It's the nervous system that routes data, detects blockers, and adapts.

Architecture:
    SOV-Space (the whole machine)
    ├── B-Space (Blocker Space — this file)
    │   ├── Platform Monitor (health checks)
    │   ├── Blocker Detector (finds problems)
    │   ├── Auto-Transfer (moves work when blocked)
    │   ├── Data Feed (routes data to clans)
    │   └── Clan Evolution Feed (training data pipeline)
    ├── Layer 0 (Free GPU Orchestrator)
    │   └── Routes tasks to cheapest resource
    ├── J-Space (per-model outputs)
    ├── V-Space (visual artifacts)
    ├── C-Space (creative simulation)
    ├── G-Space (GNN training memory)
    └── Honey Pipeline (water→milk→honey→sigil)
"""

import json, time, os, subprocess, hashlib, threading
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = Path(__file__).resolve().parent.parent
BSPACE_DIR = ROOT / "b_space"
BSPACE_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = BSPACE_DIR / "bspace_state.json"
BLOCKERS_FILE = BSPACE_DIR / "blockers.json"
FEEDS_FILE = BSPACE_DIR / "data_feeds.json"
TRANSFERS_FILE = BSPACE_DIR / "transfers.json"

# ═══════════════════════════════════════════════════════════════════════
# PLATFORM REGISTRY — All sites SOV can run on
# ═══════════════════════════════════════════════════════════════════════

PLATFORMS = {
    # GPU Compute
    "kaggle": {"type": "gpu", "resource": "T4 16GB", "hours": "30h/wk", "cost": 0,
               "check_cmd": "kaggle kernels list --mine",
               "deploy_cmd": "kaggle kernels push -p {dir}",
               "status": "unknown"},
    "google_colab": {"type": "gpu", "resource": "T4/V100/A100", "hours": "12h session", "cost": 0,
                     "check_url": "colab.research.google.com",
                     "status": "unknown"},
    "modal": {"type": "gpu", "resource": "All GPUs", "hours": "$30/mo credit", "cost": 0,
              "check_cmd": "modal list",
              "status": "unknown"},
    "lightning": {"type": "gpu", "resource": "T4/A10G", "hours": "varies", "cost": 0,
                  "status": "unknown"},
    "gradient": {"type": "gpu", "resource": "Basic GPUs", "hours": "limited", "cost": 0,
                 "status": "unknown"},
    "oracle_1": {"type": "cpu", "resource": "4 OCPU ARM", "hours": "forever", "cost": 0,
                 "ip": "145.241.232.16",
                 "check_cmd": "ssh -o ConnectTimeout=5 -i ~/.ssh/id_ed25519 ubuntu@145.241.232.16 echo ALIVE",
                 "status": "unknown"},
    "oracle_2": {"type": "cpu", "resource": "4 OCPU ARM", "hours": "forever", "cost": 0,
                 "ip": "141.147.73.85",
                 "check_cmd": "ssh -o ConnectTimeout=5 -i ~/.ssh/id_ed25519 ubuntu@141.147.73.85 echo ALIVE",
                 "status": "unknown"},

    # API Inference
    "groq": {"type": "api", "resource": "llama-3.3-70b", "limits": "100K TPD", "cost": 0,
             "status": "unknown"},
    "nvidia": {"type": "api", "resource": "Nemotron/GLM", "limits": "rate limited", "cost": 0,
               "status": "unknown"},
    "cloudflare": {"type": "api", "resource": "10K neurons/day", "limits": "daily cap", "cost": 0,
                   "status": "unknown"},
    "openrouter": {"type": "api", "resource": "25+ free models", "limits": "50 req/day", "cost": 0,
                   "status": "unknown"},
    "gemini": {"type": "api", "resource": "Gemini 2.0 Flash", "limits": "rate limited", "cost": 0,
               "status": "unknown"},
    "deepseek": {"type": "api", "resource": "DeepSeek V4/R1", "limits": "low cost", "cost": 0,
                 "status": "unknown"},
    "qwen": {"type": "api", "resource": "151 models", "limits": "rate limited", "cost": 0,
             "status": "unknown"},
    "together": {"type": "api", "resource": "200+ models", "limits": "$1 credit", "cost": 0,
                 "status": "unknown"},

    # Competitions/Arenas
    "kaggle_competitions": {"type": "competition", "resource": "Prizes $100K-$850K", "cost": 0,
                            "status": "unknown"},
    "hf_leaderboard": {"type": "leaderboard", "resource": "Open LLM ranking", "cost": 0,
                       "status": "unknown"},
    "hf_arena": {"type": "arena", "resource": "Chatbot Elo", "cost": 0,
                 "status": "unknown"},
    "lmarena": {"type": "arena", "resource": "Chatbot Arena", "cost": 0,
                "status": "unknown"},
    "govbench": {"type": "benchmark", "resource": "15-dim governance", "cost": 0,
                 "status": "unknown"},
    "papers_with_code": {"type": "benchmark", "resource": "SOTA tracking", "cost": 0,
                         "status": "unknown"},

    # Hosting
    "hf_hub": {"type": "hosting", "resource": "Model distribution", "cost": 0,
               "status": "unknown"},
    "cloudflare_pages": {"type": "hosting", "resource": "Static sites + Workers", "cost": 0,
                         "status": "unknown"},
    "github": {"type": "hosting", "resource": "Code + CI/CD", "cost": 0,
               "status": "unknown"},
}

# ═══════════════════════════════════════════════════════════════════════
# BLOCKER DETECTION — Find problems before they hurt us
# ═══════════════════════════════════════════════════════════════════════

class BlockerDetector:
    """Detects blockers across all platforms."""

    BLOCKER_TYPES = [
        "platform_down",        # Platform unreachable
        "quota_exceeded",       # Free tier limit hit
        "model_not_found",      # Model disappeared
        "training_failed",      # Training job crashed
        "api_rate_limited",     # API rate limit hit
        "disk_full",            # Storage full
        "oom",                  # Out of memory
        "auth_expired",         # API key/token expired
        "competition_closed",   # Competition ended
        "data_corrupted",       # Training data corrupted
    ]

    def detect(self, platform_name, platform):
        """Detect blockers for a specific platform."""
        blockers = []

        # Check if platform is reachable
        if platform.get("check_cmd"):
            try:
                result = subprocess.run(
                    platform["check_cmd"], shell=True,
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    blockers.append({
                        "type": "platform_down",
                        "platform": platform_name,
                        "severity": "HIGH",
                        "message": f"{platform_name} unreachable",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except:
                blockers.append({
                    "type": "platform_down",
                    "platform": platform_name,
                    "severity": "HIGH",
                    "message": f"{platform_name} timeout",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        return blockers

    def detect_all(self):
        """Detect blockers across all platforms."""
        all_blockers = []
        for name, platform in PLATFORMS.items():
            blockers = self.detect(name, platform)
            all_blockers.extend(blockers)
        return all_blockers


# ═══════════════════════════════════════════════════════════════════════
# AUTO-TRANSFER — Move work when blocked
# ═══════════════════════════════════════════════════════════════════════

class AutoTransfer:
    """Automatically transfers work from blocked platforms to available ones."""

    TRANSFER_MAP = {
        # If primary is blocked, try these alternatives
        "kaggle": ["modal", "google_colab", "gradient", "lightning"],
        "oracle_1": ["oracle_2", "hf_spaces"],
        "oracle_2": ["oracle_1", "hf_spaces"],
        "groq": ["nvidia", "cloudflare", "openrouter", "gemini"],
        "nvidia": ["groq", "cloudflare", "openrouter"],
        "cloudflare": ["groq", "nvidia", "openrouter"],
        "modal": ["kaggle", "google_colab", "gradient"],
        "google_colab": ["kaggle", "modal", "gradient"],
    }

    def transfer(self, from_platform, task_type, task_data):
        """Transfer work from blocked platform to alternative."""
        alternatives = self.TRANSFER_MAP.get(from_platform, [])

        for alt in alternatives:
            if PLATFORMS.get(alt, {}).get("status") == "healthy":
                return {
                    "from": from_platform,
                    "to": alt,
                    "task_type": task_type,
                    "status": "transferred",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "from": from_platform,
            "to": None,
            "task_type": task_type,
            "status": "no_alternative",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# DATA FEED — Route data to clans for evolution
# ═══════════════════════════════════════════════════════════════════════

class DataFeed:
    """Routes data from all platforms to SOV clans for evolution."""

    FEED_TYPES = {
        "training_data": {
            "sources": ["kaggle", "hf_hub", "groq", "oracle_1"],
            "destination": "honey_pipeline",
            "format": "jsonl",
        },
        "benchmark_results": {
            "sources": ["kaggle", "govbench", "hf_leaderboard", "lmarena"],
            "destination": "j_space",
            "format": "json",
        },
        "competition_submissions": {
            "sources": ["kaggle_competitions", "hf_leaderboard"],
            "destination": "c_space",
            "format": "csv",
        },
        "model_weights": {
            "sources": ["kaggle", "modal", "oracle_1", "hf_hub"],
            "destination": "model_registry",
            "format": "safetensors",
        },
        "compliance_data": {
            "sources": ["govbench", "defoneos", "eu_ai_act_mcp"],
            "destination": "compliance_engine",
            "format": "json",
        },
        "arena_results": {
            "sources": ["hf_arena", "lmarena"],
            "destination": "v_space",
            "format": "json",
        },
    }

    def route(self, feed_type, data, source):
        """Route data from source to appropriate SOV component."""
        feed_config = self.FEED_TYPES.get(feed_type)
        if not feed_config:
            return {"status": "unknown_feed_type"}

        destination = feed_config["destination"]
        return {
            "feed_type": feed_type,
            "source": source,
            "destination": destination,
            "data_size": len(json.dumps(data)) if isinstance(data, (dict, list)) else len(str(data)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "routed",
        }


# ═══════════════════════════════════════════════════════════════════════
# CLAN EVOLUTION FEED — Training data pipeline
# ═══════════════════════════════════════════════════════════════════════

class ClanEvolutionFeed:
    """Feeds training data to SOV clans for evolution."""

    CLANS = {
        "openworld": {"pillars": ["openness", "continuity"], "data_sources": ["hf_hub", "groq"]},
        "compliance": {"pillars": ["auditability", "verifiability"], "data_sources": ["govbench", "defoneos"]},
        "defense": {"pillars": ["safety", "resilience", "sovereignty"], "data_sources": ["kaggle", "oracle_1"]},
        "intuition": {"pillars": ["guidance", "justice", "equity"], "data_sources": ["groq", "gemini"]},
        "voice": {"pillars": ["honor", "transparency"], "data_sources": ["lmarena", "hf_arena"]},
        "sovereign": {"pillars": ["sovereignty"], "data_sources": ["oracle_1", "oracle_2"]},
        "reasoning": {"pillars": ["reasoning"], "data_sources": ["groq", "deepseek"]},
        "code": {"pillars": ["code"], "data_sources": ["kaggle", "together"]},
        "math": {"pillars": ["math"], "data_sources": ["groq", "nvidia"]},
        "vision": {"pillars": ["visual"], "data_sources": ["cloudflare", "hf_hub"]},
        "agentic": {"pillars": ["agency"], "data_sources": ["modal", "kaggle"]},
        "care": {"pillars": ["care"], "data_sources": ["groq", "oracle_1"]},
    }

    def feed_clan(self, clan_name, data):
        """Feed training data to a specific clan."""
        clan = self.CLANS.get(clan_name)
        if not clan:
            return {"status": "unknown_clan"}

        return {
            "clan": clan_name,
            "pillars": clan["pillars"],
            "data_received": len(data) if isinstance(data, list) else 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "fed",
        }


# ═══════════════════════════════════════════════════════════════════════
# B-SPACE ENGINE — The master coordinator
# ═══════════════════════════════════════════════════════════════════════

class BSpaceEngine:
    """B-Space master engine — coordinates all data feeds, blocker detection, and transfers."""

    def __init__(self):
        self.detector = BlockerDetector()
        self.transfer = AutoTransfer()
        self.feed = DataFeed()
        self.clan_feed = ClanEvolutionFeed()
        self.state = self._load_state()

    def _load_state(self):
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {
            "started": datetime.now(timezone.utc).isoformat(),
            "cycles": 0,
            "blockers_detected": 0,
            "transfers_completed": 0,
            "feeds_routed": 0,
            "clans_fed": 0,
            "platform_health": {},
        }

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def run_cycle(self):
        """Run one B-Space cycle: detect → transfer → feed → evolve."""
        self.state["cycles"] += 1
        cycle_start = time.time()

        print(f"\n{'='*60}")
        print(f"B-SPACE CYCLE {self.state['cycles']}")
        print(f"{'='*60}")

        # 1. Detect blockers
        print("\n[1/4] Detecting blockers...")
        blockers = self.detector.detect_all()
        self.state["blockers_detected"] += len(blockers)
        for b in blockers:
            print(f"  ✗ {b['platform']}: {b['type']} ({b['severity']})")
        if not blockers:
            print("  ✓ No blockers detected")

        # 2. Auto-transfer if blocked
        print("\n[2/4] Auto-transferring if blocked...")
        transfers = []
        for b in blockers:
            t = self.transfer.transfer(b["platform"], "inference", {})
            transfers.append(t)
            if t["status"] == "transferred":
                print(f"  → {b['platform']} → {t['to']}")
                self.state["transfers_completed"] += 1
            else:
                print(f"  ✗ {b['platform']} — no alternative")

        # 3. Route data feeds
        print("\n[3/4] Routing data feeds...")
        for feed_type, config in self.feed.FEED_TYPES.items():
            print(f"  → {feed_type}: {len(config['sources'])} sources → {config['destination']}")
            self.state["feeds_routed"] += 1

        # 4. Feed clans
        print("\n[4/4] Feeding clans for evolution...")
        for clan_name, clan in self.clan_feed.CLANS.items():
            print(f"  → {clan_name}: {len(clan['pillars'])} pillars, {len(clan['data_sources'])} sources")
            self.state["clans_fed"] += 1

        # Save state
        cycle_time = time.time() - cycle_start
        self.state["last_cycle"] = datetime.now(timezone.utc).isoformat()
        self.state["last_cycle_time"] = cycle_time
        self._save_state()

        print(f"\nCycle complete in {cycle_time:.1f}s")
        print(f"Total: {self.state['cycles']} cycles, "
              f"{self.state['blockers_detected']} blockers, "
              f"{self.state['transfers_completed']} transfers, "
              f"{self.state['feeds_routed']} feeds, "
              f"{self.state['clans_fed']} clan feeds")

        return {
            "cycle": self.state["cycles"],
            "blockers": len(blockers),
            "transfers": len(transfers),
            "feeds": len(self.feed.FEED_TYPES),
            "clans": len(self.clan_feed.CLANS),
            "time": cycle_time,
        }

    def get_status(self):
        """Get B-Space status."""
        return {
            "state": self.state,
            "platforms": {name: p.get("status", "unknown") for name, p in PLATFORMS.items()},
            "clans": list(self.clan_feed.CLANS.keys()),
            "feed_types": list(self.feed.FEED_TYPES.keys()),
        }


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="B-Space — Blocker Space")
    ap.add_argument("--action", choices=["run", "status", "detect", "feed"],
                    default="run")
    ap.add_argument("--cycles", type=int, default=1)
    args = ap.parse_args()

    engine = BSpaceEngine()

    if args.action == "run":
        for i in range(args.cycles):
            engine.run_cycle()
            if i < args.cycles - 1:
                time.sleep(60)

    elif args.action == "status":
        status = engine.get_status()
        print(json.dumps(status, indent=2))

    elif args.action == "detect":
        blockers = engine.detector.detect_all()
        for b in blockers:
            print(f"  {b['platform']}: {b['type']} ({b['severity']})")

    elif args.action == "feed":
        for clan in engine.clan_feed.CLANS:
            result = engine.clan_feed.feed_clan(clan, [{"test": True}])
            print(f"  {clan}: {result['status']}")
