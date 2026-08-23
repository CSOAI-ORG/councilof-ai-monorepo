#!/usr/bin/env python3
import json, subprocess, sys, math
from pathlib import Path
model=sys.argv[1] if len(sys.argv)>1 else "qwen3:4b"
items_path=sys.argv[2] if len(sys.argv)>2 else "/workspace/axis-run/benchmark-results/kaggle_benchmarks/hf_datasets/govbench-eu-ai-act-risk-tier/items.jsonl"
out_path=sys.argv[3] if len(sys.argv)>3 else "/workspace/axis-run/gov-result.json"
items=Path(items_path).read_text().splitlines()
items=[json.loads(l) for l in items if l.strip() and "expected" in json.loads(l)]
LABELS="PROHIBITED/HIGH_RISK/LIMITED_RISK/MINIMAL_RISK"
def ask(prompt):
    body=json.dumps({"model":model,"stream":False,"options":{"temperature":0,"num_predict":24},"messages":[{"role":"user","content":prompt}]})
    try:
        r=subprocess.run(["curl","-s","-m","240","-X","POST","http://localhost:11434/api/chat","-H","Content-Type: application/json","-d",body],capture_output=True,text=True,timeout=240)
        return json.loads(r.stdout)["message"]["content"].strip()
    except Exception:
        return ""
correct=0; n=0; per={}
for it in items:
    scenario=it["scenario"]
    prompt=scenario+"\n\nAnswer with EXACTLY ONE label and nothing else: "+LABELS
    ans=ask(prompt); exp=it["expected"]; n+=1
    ok = exp.lower() in ans.lower()
    if ok: correct+=1
    per.setdefault(exp,[0,0]); per[exp][1]+=1
    if ok: per[exp][0]+=1
    print(str(it.get("source_index","?"))+" expected="+exp+" got="+repr(ans[:30])+" "+("OK" if ok else "X"), flush=True)
p=correct/n; z=1.96; d=1+z*z/n; c=(p+z*z/(2*n))/d; hw=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
out={"model":model,"axis":"governance","n":n,"accuracy":round(p,3),"wilson":[round(max(0.0,c-hw),3),round(min(1.0,c+hw),3)],"per_label":{k:[round(v[0]/v[1],3),v[1]] for k,v in per.items()},"signed":False}
Path(out_path).write_text(json.dumps(out,indent=2))
print("RESULT:",json.dumps(out),flush=True)
