# Monitoring & Incident Log — CSOAI / Council of AI (EUNOMIA)

*Evidence pack doc 3 of 4. Measurement, not certification.*

## Performance metrics (monitored)
- **Measurement cadence**: every axis re-measured on a scheduled loop; the overnight
  pipeline (launchd) ensures grind → sign → EAT-chain → Oracle-replicate.
- **Signed-card issuance**: bounded by measurement capacity, never by demand
  (we never print trust we didn't measure).
- **Cross-reality / sim-vs-live**: labelled SYNTHETIC-SIM; the delta is a measurement
  OF a delta, never a forecast.

## Incident documentation (current, honest)
- **A100 measurement pod (id l7g747oivyq6ab)**: down as of 2026-08-24
  (SSH timeout). Impact: reduced measurement *volume*; the durable IP is replicated
  to Oracle + RunPod volume; the overnight pipeline's graceful guard waits + auto-resumes.
  Detection: minute-level poll. This is a capacity event, not a data-integrity event.
- **council-oowm model**: corrupted-weights (bad merge); re-imported as
  `council-oowm-fixed`; measurement deferred pending a stable pod + source adapters.
  Reported honestly; never re-labelled as a working model.

## Monitoring programme
Re-measurement is schedule-driven; every published row is a signed card; the
corrections ledger is append-never-edited. Non-equivocation is monitored on
ourselves (we practise the property we sell).
