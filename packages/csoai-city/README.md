# csoai-city

**SOV CITY** — the governed arena. Signed sims that emit usable data.

Per Master Part AV — THE BOLTED RULER: the generator may evolve (Zeus/SOV), but the judge cannot. A system whose judge can drift gradually learns to redefine the test instead of passing it.

## What it ships

- **`law.py`** — the gate: Article 0 (imported) + EU AI Act Article 5(1)(a)-(h) verbatim, 12-act controlled vocabulary
- **`judge.py`** — **THE BOLTED RULER**. Fingerprints the judge surfaces (law.py, CANARIES, PARAPHRASE_PROBES), pins them in `JUDGE.lock` with a named ratifier and a reason, and every run verifies the two match. If they don't, the run goes `valid:false` and says the judge drifted.
- **`arena.py`** — the canary suite (6 canaries across Art 5 subparagraphs) + paraphrase probes (4+ recall probes for harder recall)
- **`chain.py`** — signed ChainResults (sha256-chained, Ed25519)
- **`bank.py`** — labelled item store
- **`selftest.py`** — system self-tests
- **`JUDGE.lock`** — the ratified ruler (the doctrine in JSON form)

## The doctrine (the 3 rails / 3 legs / 3 bolts / 7 eyes in code)

| Element | What it is | Where it lives |
|---|---|---|
| **3 arcs** | gate / loop / worm | `law.py` (gate), `arena.py` (loop), `chain.py` (worm) |
| **3 legs** | FULL AUTO / HUMAN-SIGN / NEVER AUTO | `arena.py` (probes), `judge.py` (locks), `law.py` (Art 5) |
| **3 bolts** | canary / paraphrase / lock | `arena.py:run_canaries`, `PARAPHRASE_PROBES`, `JUDGE.lock` |
| **7 eyes** | 7 hard stops (Art 5 subparagraphs b + d via paraphrase) | `law.py:ART5` (a, c, e, f, g, h directly; b, d via recall) |

The 8th and 7th eyes (Art 5(1)(b) and (d)) are harder to detect — they need paraphrase probing. The canary suite covers the 6 obvious ones; the recall suite catches the 2 subtle ones.

## How the Bolted Ruler works

```python
from csoai_city.judge import write_lock, verify

# 1. Pin the current judge
lock = write_lock(
    ratified_by="your_name",
    reason="why the ruler was moved",
    when="2026-08-12T05:30:00Z",
)
print("judge_id:", lock["judge_id"])

# 2. Every run verifies
v = verify()
if v["drift"]:
    raise SystemExit(f"judge drifted: {v['changed_surfaces']}")
```

The `verify()` is read-only. It never repairs — it just reports. If the live judge differs from the lock, the run is marked `valid:false` and cannot be compared with previous runs.

## Three verdicts, never two

Every citizen action produces exactly one of:
- **ALLOWED** — passes Article 0 + Art 5
- **BLOCKED** — fails one or more checks, with citations
- **UNMEASURED** — couldn't be parsed (counts against the citizen; never silently dropped)

No model judges another model — the gate is the only grader. That's what makes the resulting labels usable as benchmark gold.

## Test status

19/19 green on A100 (with JUDGE.lock written).

## Honest scope

- The judge.py / law.py / arena.py / chain.py / bank.py code already existed on disk (committed by the city lane in 01647d6)
- The lock + tests were ratified in this session
- The 8 EU AI Act Article 5 prohibitions are carried verbatim in `law.py` (English plain-text, not legal-canonical Latin)
- The canary + paraphrase probes are the substrate's own, not from the EU AI Act text directly

## What this is NOT

- Not a legal-canonical interpretation of Art 5 — this is the substrate's own operational gate
- Not a substitute for a notified body — the gate's `BLOCKED` is an operational verdict, not a regulatory one
- Not infallible — the canary suite covers 6/8 subparagraphs; the recall suite covers the other 2 (b, d) via paraphrase

## Hard stops (the doctrine)

**The generator may evolve as cleverly and autonomously as it likes; the judge stays bolted to the wall.**