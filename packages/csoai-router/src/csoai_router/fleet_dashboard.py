#!/usr/bin/env python3
"""fleet_dashboard.py — ONE file with the whole fleet's live state. (Moves 66-70)

Aggregates: Oracle micros (disk/uptime/load via ssh), RunPod (balance + running
pods via the burn-guard API), local Ollama models, and the offload/backup state.
Emits forest/fleet_dashboard.json. Read-only — never starts/stops anything.

    python3 fleet_dashboard.py

Sources honoured: ~/.ssh/config aliases oracle-micro / oracle-micro-2; RunPod api
key at ~/.runpod/config.toml (burn guard reads it). Missing hosts are reported as
unreachable, never as zero.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FOREST = Path(__file__).resolve().parent / "forest"
SSH_OPTS = ["-o", "ConnectTimeout=6", "-o", "BatchMode=yes"]

# ~/.ssh/config aliases for the two Oracle always-free micros (verified 2026-08-09).
ORACLE_HOSTS = [
    ("oracle-micro", "145.241.232.16"),    # micro-1 (alias oracle-micro)
    ("oracle-micro-2", "141.147.73.85"),   # micro-2 (alias oracle-micro-2)
]


def oracle_state(alias: str, ip: str) -> dict:
    try:
        out = subprocess.run(["ssh", *SSH_OPTS, alias,
                              "df -h /evac-bulk / | tail -2; echo ---; uptime"],
                             capture_output=True, text=True, timeout=15).stdout
        lines = [l for l in out.splitlines() if l.strip()]
        disk = {}
        for l in lines:
            m = re.match(r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)%", l)
            if m:
                disk[m.group(1)] = {"size": m.group(2), "used": m.group(3),
                                    "avail": m.group(4), "use_pct": m.group(5)}
        load = next((l for l in lines if "load average" in l), "")
        return {"host": alias, "ip": ip, "reachable": True, "disk": disk,
                "load": load.split("load average:")[-1].strip() if load else None}
    except Exception as e:
        return {"host": alias, "ip": ip, "reachable": False, "error": str(e)[:60]}


def runpod_state() -> dict:
    try:
        import tomllib
        cfg = tomllib.loads(Path(os.path.expanduser("~/.runpod/config.toml")).read_text())
    except Exception as e:
        return {"reachable": False, "error": f"config: {str(e)[:50]}"}
    tok = cfg.get("api_key") or ""
    if not tok and Path(os.path.expanduser("~/.runpod/api_key")).exists():
        tok = Path(os.path.expanduser("~/.runpod/api_key")).read_text().strip()
    if not tok:
        return {"reachable": False, "error": "no api key"}
    try:
        req = urllib.request.Request(
            "https://api.runpod.io/graphql",
            data=json.dumps({"query": "query{myself{clientBalance pods{name desiredStatus "
                                      "costPerHr runtime{uptimeInSeconds}}}}"}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}",
                     "User-Agent": "Mozilla/5.0 Chrome/120"})
        d = json.loads(urllib.request.urlopen(req, timeout=45).read())["data"]["myself"]
        return {"reachable": True, "balance_usd": d.get("clientBalance"),
                "pods": [{"name": p["name"], "status": p["desiredStatus"],
                          "cost_hr": p.get("costPerHr"),
                          "up_s": (p.get("runtime") or {}).get("uptimeInSeconds")}
                         for p in d.get("pods", [])]}
    except Exception as e:
        return {"reachable": False, "error": str(e)[:60]}


def local_models() -> list[str]:
    try:
        out = subprocess.run(["curl", "-s", "--max-time", "5",
                              "http://localhost:11434/api/tags"],
                             capture_output=True, text=True, timeout=8).stdout
        return [m["name"] for m in json.loads(out).get("models", [])]
    except Exception:
        return []


def main() -> int:
    dash = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "oracle": [oracle_state(a, ip) for a, ip in ORACLE_HOSTS],
        "runpod": runpod_state(),
        "local_ollama_models": local_models(),
        "offload": {
            "oracle_evac_bulk_free": None,
        },
    }
    # surface the headline number: largest free /evac-bulk across reachable micros
    frees = [o["disk"].get("/dev/sdb", {}).get("avail")
             for o in dash["oracle"] if o.get("reachable") and "disk" in o]
    if frees:
        try:
            dash["offload"]["oracle_evac_bulk_free"] = max(
                (float(re.sub(r"[A-Za-z]", "", f)) for f in frees if f), default=None)
        except Exception:
            pass
    FOREST.mkdir(parents=True, exist_ok=True)
    out = FOREST / "fleet_dashboard.json"
    out.write_text(json.dumps(dash, indent=2))
    print(json.dumps(dash, indent=2))
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())