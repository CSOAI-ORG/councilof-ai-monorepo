# Technical System Description — CSOAI / Council of AI (EUNOMIA)

*Evidence pack doc 1 of 4 (core underwriter set). Measurement, not certification.*

## What the system does
CSOAI is an independent AI-governance **measurement** body. Its primary system
(EUNOMIA) measures AI-governance compliance outcomes via **frozen, exact-label
benchmarks** run against publicly-available AI models, producing an **Ed25519-signed
measurement card** per axis (accuracy, Wilson 95% CI, item count, label set).

## The model(s)
Measurement is model-agnostic by design. The EUNOMIA engine runs a frozen item bank
governance/flux: two tiers are measured today — a small baseline (qwen2.5:0.5b) and a
strong tier (qwen2.5:7b) — plus the estate's own models where observable. The engine
does **not** train or fine-tune models; it measures them.

## The data
Frozen item sets (the "bank") — gold-labelled scenarios per governance axis, pinned
to a hash. Ten financial-verification axes (governance, bond-router, insurance,
stock-market, east-west, sme-fractional, agent-economy, data-dao, eunomia-token,
climate-transition, privacy-risk), 102+ gold-labelled items, each with a canary
anchor for contamination detection. Licence: CC0-1.0, licence-swept before ingestion.

## The outputs
An Ed25519-signed measurement card per axis: accuracy, Wilson 95% CI, item count,
label set, frozen-bank version hash, signer. The card states **what was measured,
when, against which frozen bank**, and what it never proves (quality verdict,
compliance determination, investment relevance). Cards are recompute-able.

## Scope
Measurements are produced from **public** artifacts + permissionless/registration-class
public endpoints. The system never penetrates, never scrapes against terms, never
measures a private system it was not handed. No intrusion; licence-sweep first.
