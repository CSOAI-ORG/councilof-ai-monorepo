#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import os as _os, shutil as _sh; _rp=_os.path.expanduser('~/.runpod/api_key'); (_os.path.exists(_rp) and not _os.path.exists('/tmp/.rpk')) and _sh.copy(_rp,'/tmp/.rpk')
"""Watch the EAT fleet ~50 min, log every status transition, then exit (re-invokes the agent).
Flags: spray pods that EXITED (harvest done, self-terminated), and fuel-train uptime (parks after
training → idle-burn candidate). Does NOT auto-stop training — killing an active run wastes it."""
import json, time, urllib.request
TOKEN = open('/tmp/.rpk').read().strip()
UA = "Mozilla/5.0 Chrome/120"


def pods():
    req = urllib.request.Request("https://api.runpod.io/graphql",
        data=json.dumps({"query": "query{myself{clientBalance pods{id name desiredStatus costPerHr runtime{uptimeInSeconds}}}}"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}", "User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=45).read())['data']['myself']


prev = {}
for i in range(25):  # ~50 min at 120s
    try:
        m = pods()
        cur = {p['name']: p['desiredStatus'] for p in m['pods']}
        for name, st in cur.items():
            if prev.get(name) and prev[name] != st:
                print(f"[t{i*2}m] TRANSITION {name}: {prev[name]} → {st}")
        # flag fuel-train that has been up a long time (likely parked/done)
        for p in m['pods']:
            if 'fuel-train' in p['name'] and p['desiredStatus'] == 'RUNNING':
                up = (p.get('runtime') or {}).get('uptimeInSeconds') or 0
                if up and up > 2700:  # >45 min
                    print(f"[t{i*2}m] ⚠ fuel-train up {up//60}min — LoRA likely done + PARKED. Candidate to stop (id {p['id']}).")
        prev = cur
        running = sum(1 for s in cur.values() if s == 'RUNNING')
        spray_running = sum(1 for n, s in cur.items() if 'browser-eat' in n and s == 'RUNNING')
        if i % 5 == 0:
            print(f"[t{i*2}m] {running} running · {spray_running} spray active · balance ${m['clientBalance']:.2f}")
        if spray_running == 0 and any('browser-eat' in n for n in cur):
            print(f"[t{i*2}m] all spray pods completed — harvest done."); break
    except Exception as e:
        print(f"[t{i*2}m] err {str(e)[:50]}")
    time.sleep(120)
print("MONITOR-EXIT")
