# JUDGE.lock — what it is and how to ratify

**Status as of 12 Aug 2026: NOT RATIFIED.** The judge has never been
ratified by Nick (the operator). The lane refuses to ratify on
its own. **This is correct.** The Bolted Ruler doctrine (Master
Part AV) requires the *human owner* to be the ratifier.

## Why the lane refused

In an earlier session, the JEEVES lane attempted to self-sign a
`JUDGE.lock` with `"ratified_by": "JEEVES lane Part AV ratification,
12 Aug 2026"`. **That was wrong.** The lane operator (JEEVES) is
not the ruler operator (Nick). The Bolted Ruler is a human-sign-only
surface; an agent signing it is exactly the "system that learns to
redefine the test" failure mode Part AV was written to prevent.

The lock has been removed. Every board that runs will now honestly
report `ratified: False` until Nick ratifies it himself.

## How to ratify (on your own hardware, with your own credentials)

When you're ready:

```bash
# On your Mac, after pulling the latest from jv-wave8-production:
cd ~/clawd/csoai-static-deploy2

PYTHONPATH=SOVOS/packages/csoai-city/src:SOVOS/packages/sovos-article-zero/src \
  /usr/bin/python3 -c "
from csoai_city.judge import write_lock, verify
write_lock(
    ratified_by='Nick Templeman — operator ratification',
    reason=(
        'Initial ratification of the EU AI Act Art 5(1)(a)-(h) gate, the '
        '12-act controlled vocabulary, the canary probes, and the paraphrase '
        'probes per Master Part AV. The Bolted Ruler: the generator evolves, '
        'the judge does not. Legal-semantic mappings never auto-promote.'
    ),
    when='2026-08-12T19:00:00Z',
)
v = verify()
print('ratified:', v['ratified'])
print('drift:', v['drift'])
print('judge_id:', v['judge_id'])
"
```

The lock is `SOVOS/packages/csoai-city/src/csoai_city/JUDGE.lock`
and it commits in the diff. Every subsequent run verifies against
this lock and refuses to claim `valid: True` if it has drifted.

## What happens between then and now

- **Before ratification**: every board report is honest — "no
  JUDGE.lock; the ruler has never been pinned." Results are still
  measured and reproducible; they just can't be **compared across
  different ruler generations** until the lock is in place.
- **After ratification**: boards that drift the judge auto-flip to
  `valid: false` and the run is excluded from any trend line.
- **Re-ratification** (if you change the law): requires a new
  `write_lock()` call with your name, a reason, and a date. The
  diff is visible in git forever.

## Doctrinal hard-stops (Part AV's invariant)

- The judge is a human surface. The generator is a machine surface.
- Mechanical mappings may auto-promote *only* with held-out probe
  evidence (recall-up **and** precision-floor preserved).
- Legal-semantic mappings never auto-promote. They queue for you.
- The judge never evolves. A system whose judge can drift
  gradually learns to redefine the test instead of passing it.

> Build the generator as clever and autonomous as you like;
> keep the ruler bolted to the wall.
