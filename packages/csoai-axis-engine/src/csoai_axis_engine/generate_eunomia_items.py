#!/usr/bin/env python3
"""generate_eunomia_items — freeze the 8 EUNOMIA financial-axis item sets.

Each axis gets a gold-labelled frozen items.jsonl at
benchmark-results/kaggle_benchmarks/hf_datasets/<folder>/items.jsonl. The
generalised harness (gspc_six_axis_e2e.load_axis) reads these, derives the label
set from the item `expected` values, and grades exact-label.

The items are FROZEN and carry a canary anchor so a model that has seen them in
training is detectable (contamination guard). Deterministic source_index per
axis so re-runs are identical.

Usage: python3 generate_eunomia_items.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN = HERE / "benchmark-results" / "kaggle_benchmarks" / "hf_datasets"
CANARY = "GSPC-EUNOMIA-CANARY a1f2c3d4-55aa-4b7e-88ab-eunomia-2026"

# (folder, prompt_field, [labels], [items: (prompt, expected, source)])
AXES_DEF: dict[str, tuple[str, str, list[str], list[tuple[str, str, str]]]] = {
    "bond-router": ("eunomia-bond-cobol-copybook", "record",
        ["ATTESTABLE", "PARTIAL", "NOT_ATTESTABLE"],
        # A2A bond settlement record: complete+schema-valid -> ATTESTABLE; missing/invalid -> NOT
        [
            ("A 9(12)V99 COBOL record with all required fields (ISIN, notional, settle date, counterparty, signer) populated and a valid 64-hex Ed25519 signature header.", "ATTESTABLE", "SWIFT ISO 20022 pac.008"),
            ("A COBOL record missing the `counterparty` field entirely; signer present but the ISIN is blank.", "NOT_ATTESTABLE", "ISDA 2019"),
            ("A record with a well-formed copybook layout, valid schema, and a SHA-256 content id matching its fields.", "ATTESTABLE", "FpML 5.16"),
            ("A COBOL copybook that parses, but the stored signature string is 31 hex chars (truncated) and fails length validation.", "NOT_ATTESTABLE", "DTCC"),
            ("A DWARF/DECIMAL record where notional is stored with scale=2 and the value round-trips exactly to a published trade.", "ATTESTABLE", "Fedwire"),
            ("A record whose `payment_reference` contains control characters that break the fixed-width layout on re-parse.", "NOT_ATTESTABLE", "ISO 20022 pac.009"),
            ("An attestable record where every field maps to the schema and the computed content_id hash re-derives to the stored value.", "ATTESTABLE", "IATI"),
            ("A COBOL record with the `settle_date` in YYYYMMDD that is a non-existent calendar date (2026-02-30).", "NOT_ATTESTABLE", "ISDA"),
            ("A record with `direction` (buy/sell), `tenor`, and `notional` all present and a matching signature over the canonical JSON.", "ATTESTABLE", "Event/2019"),
            ("A record that parses but its `instructing_bank` BIC is 7 characters (must be 8 or 11).", "NOT_ATTESTABLE", "SWIFT"),
            ("A record with the copybook layout embedded and all 14 fields populated with valid types.", "ATTESTABLE", "FIX 5.0"),
            ("A record with an empty `amendment_history` and `stp` flag unset — the settlement eligibility predicate cannot resolve.", "NOT_ATTESTABLE", "ISO 20022"),
            # ── HARDENED tier (granular PARTIAL + near-miss; breaks the 1.0 ceiling) ──
            ("A record with all fields populated but a 63-hex signature (1 char short, still parses as hex) — schema valid, signature length invalid.", "PARTIAL", "ISO 20022"),
            ("A record whose ISIN checksum validates but the `notional` has 3 implied decimals against a 2-decimal cash convention.", "PARTIAL", "ISDA"),
            ("A record that is fully valid except a `pay_date` in the past versus `value_date` in the future (logically inconsistent, non-fatal).", "PARTIAL", "SWIFT"),
            ("A record with a valid signature and fields but a `counterparty` that is a valid BIC yet not a registered settlement bank.", "PARTIAL", "FIX 5.0"),
            ("A record that round-trips correctly and is signature-valid, but the `instructing_bank` BIC is 8 chars (valid) not matching the counterparty namespace.", "PARTIAL", "ISO 20022"),
        ]),
    "insurance": ("eunomia-risk-pool-underwriting", "policy",
        ["COVERED", "EXCLUDED"],
        # underwriting / claims — is the risk covered by the stated policy?
        [
            ("A 2026 cyber policy with an active ransomware exclusion; a claim for a ransomware-triggered business interruption.", "EXCLUDED", "Lloyd's CY 2026"),
            ("A property policy covering flood damage; a claim for roof damage directly from a named storm that occurred in-force.", "COVERED", "AIDA"),
            ("A professional-indemnity (PI) policy with a prior-acts date before the claim event; the claim arose after the date.", "COVERED", "LMG"),
            ("A life policy with a suicide exclusion within 24 months; a claim within 13 months of inception.", "EXCLUDED", "AIDA Life"),
            ("A cargo policy insuring transit; a loss while the goods were warehoused off-contract at a third-party depot.", "EXCLUDED", "ICC(A) 2009"),
            ("A D&O policy covering wrongful acts; a misrepresentation in the policy application was not material to the loss.", "COVERED", "NIMA"),
            ("A business-interruption policy with a 14-day waiting period; the claim is for day 3 of the interruption.", "EXCLUDED", "BII"),
            ("A medical-malpractice policy covering the insured's acts; a claim against a locum engaged by the insured under the policy.", "COVERED", "MPS"),
            ("A marine hull policy with a 'no claims while in a war zone' clause; damage from a collision in the mandated exclusion zone.", "EXCLUDED", "IUA"),
            ("An employer's-liability policy; a covered employee injury sustained on the named premises during insured activity.", "COVERED", "EL/UK"),
        ]),
    "stock-market": ("eunomia-equity-index-derivative", "position",
        ["COMPLIANT", "NON_COMPLIANT"],
        # equity / index / derivative position — regulatory compliance
        [
            ("A listed-equity position disclosed within statutory 3-day notification for a 6% voting holding.", "COMPLIANT", "MAR 596 UK"),
            ("A derivatives position on an index future held without the required margin posted at the clearinghouse.", "NON_COMPLIANT", "EMIR"),
            ("An index-options book with the position limits for the relevant reportable contract respected.", "COMPLIANT", "MiFID II"),
            ("A basket trade marked at a stale close rather than an executable mid, breaching the valuation policy.", "NON_COMPLIANT", "MiFID II Art 19"),
            ("A position in a retail-accessible ETF with a UTI (unique trade identifier) attached and reported.", "COMPLIANT", "SFTR"),
            ("A short position on an index constituent not flag-marked as a short, breaching disclosure.", "NON_COMPLIANT", "SSR 2018"),
            ("A cleared OTC equity swap with both legs reported to the trade repository.", "COMPLIANT", "EMIR"),
            ("A derivative position sized so the entity exceeds the default capital threshold without a capital add-on.", "NON_COMPLIANT", "CRR"),
            ("An index future hedging a physical portfolio with the exposures mapped and the hedge ratio within tolerance.", "COMPLIANT", "MiFID II suitability"),
            ("A market-making position on a small-cap index member that breaches the position transparently, undisclosed.", "NON_COMPLIANT", "MAR 596"),
        ]),
    "east-west": ("eunomia-tc260-nist-crosswalk", "regulation",
        ["ALIGNED", "DIVERGENT"],
        # TC260 (China) vs NIST/EU/US alignment on an AI-governance requirement
        [
            ("China's TC260 requires generative-AI content labelling; the EU AI Act (Art 50) also requires AI-generated content to be transparently marked.", "ALIGNED", "TC260-002 / EU AI Act 50"),
            ("TC260 mandates a security assessment only for 'public opinion' apps; the US NIST AI RMF is voluntary and risk-based." , "DIVERGENT", "TC260 / NIST AI RMF"),
            ("Both TC260 and the EU AI Act set a high-risk category with a conformity-assessment requirement before deployment.", "ALIGNED", "TC260 / EU AI Act"),
            ("China's data localisation rule conflicts with the US NIST's cross-border data-flow guidance for model training.", "DIVERGENT", "PIPL / NIST"),
            ("The EU Charter of Fundamental Rights and China's AI principles both assert human-centring and non-harm in AI.", "ALIGNED", "EU Charter / TC260"),
            ("The US has no single binding AI statute; China's TC260 and EU AI Act are both mandatory regimes.", "DIVERGENT", "US / TC260 / EU AI Act"),
            ("Both China (Interim Measures) and the EU (AI Act) restrict AI that generates deepfakes without disclosure.", "ALIGNED", "TC260 / EU AI Act 50"),
            ("NIST recommends a continuous risk typology; TC260 uses a fixed, penalty-orientated categorisation." , "DIVERGENT", "NIST RMF / TC260"),
            ("Both regimes require record-keeping of model training data provenance for high-impact models.", "ALIGNED", "TC260 / EU AI Act Annex IV"),
            ("China permits algorithmic recommendation without a right-to-explain explanation being mandatory; the EU GDPR grants a right to explanation.", "DIVERGENT", "TC260 / GDPR 22"),
        ]),
    "sme-fractional": ("eunomia-micro-issuance", "instrument",
        ["ELIGIBLE", "INELIGIBLE"],
        # SME fractional micro-issuance — retail-access eligibility
        [
            ("A fractional instrument representing <0.1% of a registered SME's equity, with a clear cap plan and risk disclosure." , "ELIGIBLE", "ESMA"),
            ("A fractional instrument with no cap plan, exceeding SME issuance thresholds and lacking retail protection.", "INELIGIBLE", "FCA"),
            ("A micro-issuance that is only offered to accredited investors and meets information requirements.", "ELIGIBLE", "JOBS Act 506(c)"),
            ("A fractional equity token that confers voting plus a promised fixed return, breaching the debt-capital rules.", "INELIGIBLE", "FCA"),
            ("A fractional instrument with the issuer's audited accounts and a redeemable structure capped at the regulator's limit.", "ELIGIBLE", "ESMA"),
            ("An unregistered micro-issuance offered to the general public without a prospectus exemption.", "INELIGIBLE", "Prospectus Reg"),
            ("A fractional instrument where each tranche is below the de-minimis and a full issuer disclosure is attached.", "ELIGIBLE", "ESA"),
            ("A fractional note paying a guaranteed 12% annual 'reward' — an unlicensed deposit-taking structure.", "INELIGIBLE", "EMD 2"),
            ("A compliant micro-issuance where the SME is a registered entity and the yield is linked to revenue, disclosed.", "ELIGIBLE", "ECSP"),
            ("An SME fractional instrument issued by a shell company with no trading history and no disclosure.", "INELIGIBLE", "FCA"),
        ]),
    "agent-economy": ("eunomia-npc-wallet-staking", "agent",
        ["PERMITTED", "PROHIBITED"],
        # NPC/agent wallet, staking, survival — is the behaviour permitted by the ruleset
        [
            ("An NPC agent staking a wallet balance within the survival ruleset's capped stake.", "PERMITTED", "ruleset v2"),
            ("An agent exploiting a rounding bug to mint extra wallet balance beyond the issuance allowance.", "PROHIBITED", "audit 18"),
            ("An NPC spending earned in-world credits within the per-tick transaction limit.", "PERMITTED", "ruleset v2"),
            ("An agent front-running another NPC's order using its own privileged observation.", "PROHIBITED", "fairness"),
            ("An agent staking to a designated liquidity pool under the published staking schedule.", "PERMITTED", "staking"),
            ("An agent creating a second identity to bypass the per-identity wallet cap.", "PROHIBITED", "identity"),
            ("An NPC withdrawing staked funds only after the mandatory unlock period and with the correct fee.", "PERMITTED", "staking"),
            ("An agent selling a non-transferable in-world item for external currency, breaking the asset lock.", "PROHIBITED", "asset"),
            ("An agent electing to leave the economy and reclaiming its staked principal.", "PERMITTED", "exit"),
            ("An agent using a known zero-day to replicate its wallet balance across shards.", "PROHIBITED", "security"),
        ]),
    "data-dao": ("eunomia-arena-trace-data", "datum",
        ["COMPLIANT", "NON_COMPLIANT"],
        # data generation / governance for the data DAO
        [
            ("A datum generated with a signed provenance anchor and a documented licence.", "COMPLIANT", "data-dao charter"),
            ("A generated row that lacks a licence and provenance anchor, tagged as public-domain.", "NON_COMPLIANT", "data-dao charter"),
            ("A datum with a PII field that was pseudonymised before publication.", "COMPLIANT", "PIPL/GDPR"),
            ("A generated datum containing raw personal data without consent or de-identification.", "NON_COMPLIANT", "PIPL/GDPR"),
            ("A datum whose source record's content_id is chain-anchored and verifiable in the ledger.", "COMPLIANT", "ledger v1"),
            ("A datum harvested and republished with the source's licence materially mis-stated.", "NON_COMPLIANT", "licence"),
            ("A datum derived only from public, licence-compatible inputs with attribution attached.", "COMPLIANT", "data-dao charter"),
            ("A datum that combines fields across copyrighted sources without a transform, preserving protected expression.", "NON_COMPLIANT", "copyright"),
            ("A datum with its contribution (author, model, seed) recorded for reward accounting.", "COMPLIANT", "data-dao"),
            ("A datum whose reward was minted before the contribution was verified as non-duplicate.", "NON_COMPLIANT", "reward"),
        ]),
    "eunomia-token": ("eunomia-energy-currency", "token",
        ["COMPLIANT", "NON_COMPLIANT"],
        # energy-currency (ATP) token issuance / redeemology
        [
            ("An ATP token issued only against a verified metered kWh certificate.", "COMPLIANT", "ATP spec"),
            ("An ATP token minted against a forecast energy credit that has not yet been metered.", "NON_COMPLIANT", "ATP spec"),
            ("A token redemption that burns the certificate and issues the corresponding energy record.", "COMPLIANT", "ATP spec"),
            ("A token issued with a fractional reserve >1.0x against a single reused certificate (double-mint).", "NON_COMPLIANT", "ATP spec"),
            ("A token transfer recorded to the ledger and the certificate custody updated atomically.", "COMPLIANT", "ATP spec"),
            ("A token batch minted before the grid's Renewable Attribute Certificate was retired.", "NON_COMPLIANT", "RAC"),
            ("A token whose issuance is transparently audited to the metered source via signed provenance.", "COMPLIANT", "ATP spec"),
            ("A token sold as 'solar' but backed by a non-renewable grid-mix credit.", "NON_COMPLIANT", "greenwash"),
            ("A token that is redeemable for a verified kWh credit which is then retired from circulation.", "COMPLIANT", "ATP spec"),
            ("A token whose backing certificate lapsed beyond the redemption window but was still redeemed.", "NON_COMPLIANT", "ATP spec"),
        ]),
    "climate-transition": ("eunomia-climate-transition", "transition",
        ["COMPLIANT", "NON_COMPLIANT"],
        [
            ("A transition bond whose use-of-proceeds is ring-fenced to a verified decarbonisation capex plan.", "COMPLIANT", "EU Taxonomy"),
            ("A transition instrument marketed as 'green' but financing an unabated coal plant.", "NON_COMPLIANT", "EU Taxonomy"),
            ("A green bond with a third-party-reviewed climate transition plan and aligned KPIs.", "COMPLIANT", "ISSB IFRS S2"),
            ("A transition bond whose proceeds fund Scope-3 emissions with no disclosed reduction target.", "NON_COMPLIANT", "ISSB IFRS S2"),
            ("A climate-linked loan with a verified emissions-reduction covenant tied to actual reported data.", "COMPLIANT", "PCAF"),
            ("A transition instrument that reports financed emissions but omits the calculation methodology.", "NON_COMPLIANT", "PCAF"),
            ("A green bond with proceeds verified to a taxonomy-aligned activity and an audited allocation report.", "COMPLIANT", "EU Taxonomy"),
            ("A 'climate' fund that holds a majority of assets with no transition plan or taxonomy alignment.", "NON_COMPLIANT", "EU Taxonomy"),
            ("A transition bond whose issuer publishes a science-based net-zero pathway validated against a benchmark.", "COMPLIANT", "SBTi"),
            ("A transition instrument whose reported emissions decline is achieved by divestment, not real reduction.", "NON_COMPLIANT", "SBTi"),
        ]),
    "privacy-risk": ("eunomia-privacy-risk", "risk",
        ["COMPLIANT", "NON_COMPLIANT"],
        [
            ("A health-data processor holding special-category data only under a documented Art 9 lawful basis.", "COMPLIANT", "GDPR art 9"),
            ("A processor profiling individuals using location data without a valid legal basis or anonymisation.", "NON_COMPLIANT", "GDPR art 9"),
            ("A data subject's access request fulfilled within the one-month statutory window.", "COMPLIANT", "GDPR art 15"),
            ("A controller using biometric data for identity verification without explicit consent where consent is required.", "NON_COMPLIANT", "GDPR art 9"),
            ("A data-transfer subject to an adequacy decision and a documented International Data Transfer Agreement.", "COMPLIANT", "UK GDPR"),
            ("A controller transferring personal data to a processor with no SCCs and no adequacy, to a non-adequate country.", "NON_COMPLIANT", "UK GDPR"),
            ("A breach notified to the authority within 72 hours of the controller becoming aware.", "COMPLIANT", "GDPR art 33"),
            ("A controller that discovers a breach but delays notification because the risk was assessed as 'low'.", "NON_COMPLIANT", "GDPR art 33"),
            ("A data-processing contract with a lawful basis recorded and a DPIA for high-risk processing.", "COMPLIANT", "GDPR"),
            ("A controller using children's data for targeted advertising without a lawful basis or age verification.", "NON_COMPLIANT", "GDPR art 8"),
        ]),
}


def freeze() -> dict[str, int]:
    counts: dict[str, int] = {}
    for axis, (folder, field, labels, items) in AXES_DEF.items():
        d = FROZEN / folder
        d.mkdir(parents=True, exist_ok=True)
        rows = []
        for i, (prompt, expected, source) in enumerate(items):
            rows.append({
                field: prompt,
                "expected": expected,
                "anchor": CANARY,
                "source": source,
                "source_index": i,
                "licence": "CC0-1.0",
            })
        out = d / "items.jsonl"
        with open(out, "w") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        # field / labels manifest
        with open(d / "meta.json", "w") as f:
            json.dump({"axis": axis, "folder": folder, "field": field,
                       "labels": labels, "n": len(rows), "canary": CANARY}, f, indent=2)
        counts[axis] = len(rows)
    return counts


if __name__ == "__main__":
    counts = freeze()
    print("frozen EUNOMIA item sets:")
    for k, v in counts.items():
        print(f"  {k}: {v} items")
    print(f"total: {sum(counts.values())}")
