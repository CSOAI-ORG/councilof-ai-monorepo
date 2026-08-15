"""
DISTRIBUTED STIGMERGY: No Central Bottleneck

Architecture:
- Each hive has its own LOCAL stigmergy layer
- Signals propagate PEER-TO-PEER between hives
- Gossip protocol for cross-hive communication
- No single point of failure
- Self-organizing pheromone trails

Three signal types (insect-inspired):
1. PHEROMONE (ants): Indirect coordination through environment
   - Local trails per hive, merged via gossip
   - Evaporation prevents stale signals

2. WAGGLE (bees): Direct communication of location/direction
   - Encodes "where the good stuff is"
   - Propagated via gossip to all hives

3. POLLEN (bees): Knowledge transfer
   - Carries knowledge between brains
   - Routed through gossip network

GOSSIP PROTOCOL:
- Each hive gossips to 2-3 random neighbors every beat
- Gossip includes: pheromone trails, waggle dances, pollen grains
- Merging: stronger signals win, weaker signals evaporate
- No central coordinator needed

SPINE DRUM (distributed):
- Each hive has its own local heartbeat
- Syncs with neighbors via gossip
- No central clock needed
"""
import json, time, random, math, threading, hashlib
from pathlib import Path
from datetime import datetime
from collections import defaultdict

IWM_DIR = Path(__file__).resolve().parent


class LocalStigmergy:
    """Local stigmergy for a single hive."""

    def __init__(self, hive_name):
        self.hive_name = hive_name
        self.pheromone_trails = {}
        self.waggle_dances = []
        self.pollen_grains = []
        self.evaporation_rate = 0.02
        self.gossip_count = 0

    def propagate(self, clan_results):
        """Propagate signals within this hive."""
        for clan_name, clan_result in clan_results.items():
            confidence = clan_result.get("confidence", 0)
            best_fam = clan_result.get("c_space", {}).get("best_family", "unknown")

            # PHEROMONE: Local trail
            trail_key = f"{clan_name}:{best_fam}"
            if trail_key not in self.pheromone_trails:
                self.pheromone_trails[trail_key] = {"strength": 0, "count": 0, "last_update": None}
            self.pheromone_trails[trail_key]["strength"] += confidence
            self.pheromone_trails[trail_key]["count"] += 1
            self.pheromone_trails[trail_key]["last_update"] = datetime.now().isoformat()

            # WAGGLE: Direct signal
            waggle = {
                "source": f"{self.hive_name}:{clan_name}",
                "best_family": best_fam,
                "confidence": confidence,
                "direction": "toward" if confidence > 0.5 else "away",
                "timestamp": datetime.now().isoformat(),
            }
            self.waggle_dances.append(waggle)

            # POLLEN: Knowledge transfer
            pollen = {
                "source": f"{self.hive_name}:{clan_name}",
                "knowledge": {"confidence": confidence, "best_family": best_fam},
                "timestamp": datetime.now().isoformat(),
            }
            self.pollen_grains.append(pollen)

        self._evaporate()

    def _evaporate(self):
        """Evaporate old pheromone trails."""
        for key in list(self.pheromone_trails.keys()):
            trail = self.pheromone_trails[key]
            trail["strength"] *= (1 - self.evaporation_rate)
            if trail["strength"] < 0.01:
                del self.pheromone_trails[key]

    def get_gossip_payload(self):
        """Get data to gossip to neighbors."""
        return {
            "hive": self.hive_name,
            "pheromone": dict(self.pheromone_trails),
            "waggle": self.waggle_dances[-10:],  # Last 10
            "pollen": self.pollen_grains[-10:],  # Last 10
            "timestamp": datetime.now().isoformat(),
        }

    def merge_gossip(self, payload):
        """Merge gossip from a neighbor."""
        self.gossip_count += 1
        # Merge pheromone trails
        for key, trail in payload.get("pheromone", {}).items():
            if key not in self.pheromone_trails:
                self.pheromone_trails[key] = trail
            else:
                # Stronger signal wins
                if trail["strength"] > self.pheromone_trails[key]["strength"]:
                    self.pheromone_trails[key] = trail
        # Merge waggle dances
        self.waggle_dances.extend(payload.get("waggle", []))
        self.waggle_dances = self.waggle_dances[-50:]  # Keep last 50
        # Merge pollen grains
        self.pollen_grains.extend(payload.get("pollen", []))
        self.pollen_grains = self.pollen_grains[-50:]  # Keep last 50

    def get_strongest_trails(self, top_n=5):
        return sorted(
            self.pheromone_trails.items(),
            key=lambda x: x[1]["strength"] / max(x[1]["count"], 1),
            reverse=True,
        )[:top_n]

    def get_status(self):
        return {
            "hive": self.hive_name,
            "pheromone_trails": len(self.pheromone_trails),
            "waggle_dances": len(self.waggle_dances),
            "pollen_grains": len(self.pollen_grains),
            "gossip_received": self.gossip_count,
        }


class GossipProtocol:
    """Gossip protocol for peer-to-peer stigmergy propagation."""

    def __init__(self, hives):
        self.hives = hives  # Dict of hive_name -> LocalStigmergy
        self.gossip_log = []
        self.round = 0

    def gossip_round(self):
        """One round of gossip: each hive talks to 2-3 random neighbors."""
        self.round += 1
        hive_names = list(self.hives.keys())
        if len(hive_names) < 2:
            return

        for hive_name in hive_names:
            # Pick 2-3 random neighbors
            neighbors = random.sample([h for h in hive_names if h != hive_name], min(3, len(hive_names) - 1))
            payload = self.hives[hive_name].get_gossip_payload()

            for neighbor in neighbors:
                self.hives[neighbor].merge_gossip(payload)
                self.gossip_log.append({
                    "round": self.round,
                    "from": hive_name,
                    "to": neighbor,
                    "timestamp": datetime.now().isoformat(),
                })

    def get_status(self):
        return {
            "rounds": self.round,
            "total_gossip": len(self.gossip_log),
            "hive_count": len(self.hives),
        }


class DistributedSpineDrum:
    """Distributed Spine Drum: each hive has its own heartbeat, synced via gossip."""

    def __init__(self):
        self.local_beats = {}  # hive_name -> beat_count
        self.sync_log = []
        self.total_beats = 0

    def beat(self, hive_name, results=None):
        """Local heartbeat for a specific hive."""
        if hive_name not in self.local_beats:
            self.local_beats[hive_name] = 0
        self.local_beats[hive_name] += 1
        self.total_beats += 1
        return {
            "hive": hive_name,
            "beat": self.local_beats[hive_name],
            "total_beats": self.total_beats,
            "timestamp": datetime.now().isoformat(),
        }

    def sync_neighbors(self, hive_a, hive_b):
        """Sync two hives' heartbeats."""
        beat_a = self.local_beats.get(hive_a, 0)
        beat_b = self.local_beats.get(hive_b, 0)
        # Average the beats
        avg = (beat_a + beat_b) // 2
        self.local_beats[hive_a] = avg
        self.local_beats[hive_b] = avg
        self.sync_log.append({
            "hive_a": hive_a, "hive_b": hive_b,
            "synced_to": avg, "timestamp": datetime.now().isoformat(),
        })

    def get_status(self):
        return {
            "hives": len(self.local_beats),
            "total_beats": self.total_beats,
            "beats_per_hive": dict(self.local_beats),
        }


class DistributedStigmergy:
    """Distributed Stigmergy: no central bottleneck."""

    def __init__(self):
        self.local_stigmergies = {}
        self.gossip = None
        self.spine_drum = DistributedSpineDrum()

    def init_hives(self, hive_names):
        """Initialize local stigmergy for each hive."""
        for name in hive_names:
            self.local_stigmergies[name] = LocalStigmergy(name)
        self.gossip = GossipProtocol(self.local_stigmergies)

    def propagate(self, hive_name, clan_results):
        """Propagate signals within a specific hive."""
        if hive_name in self.local_stigmergies:
            self.local_stigmergies[hive_name].propagate(clan_results)
            self.spine_drum.beat(hive_name)

    def gossip_round(self):
        """Run one round of gossip between all hives."""
        if self.gossip:
            self.gossip.gossip_round()

    def get_global_trails(self, top_n=10):
        """Get strongest pheromone trails across all hives."""
        all_trails = {}
        for hive_name, stig in self.local_stigmergies.items():
            for key, trail in stig.pheromone_trails.items():
                global_key = f"{hive_name}:{key}"
                all_trails[global_key] = trail
        return sorted(all_trails.items(), key=lambda x: x[1]["strength"] / max(x[1]["count"], 1), reverse=True)[:top_n]

    def get_global_waggle(self):
        """Get waggle dance summary across all hives."""
        all_waggle = []
        for stig in self.local_stigmergies.values():
            all_waggle.extend(stig.waggle_dances)
        toward = sum(1 for w in all_waggle if w.get("direction") == "toward")
        away = sum(1 for w in all_waggle if w.get("direction") == "away")
        return {"total": len(all_waggle), "toward": toward, "away": away}

    def get_status(self):
        return {
            "hives": len(self.local_stigmergies),
            "gossip": self.gossip.get_status() if self.gossip else None,
            "spine_drum": self.spine_drum.get_status(),
            "local_status": {name: stig.get_status() for name, stig in self.local_stigmergies.items()},
            "global_trails": len(self.get_global_trails()),
        }
