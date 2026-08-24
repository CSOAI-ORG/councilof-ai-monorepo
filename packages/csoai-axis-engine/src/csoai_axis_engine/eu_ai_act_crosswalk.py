"""EU AI Act full-article crosswalk — the "find every problem for every AI company" engine.

Maps the EU AI Act (Reg. (EU) 2024/1689) articles to GSPC/EUNOMIA axes, the
requirement they impose, and the regulatory exposure. The white-label tool uses
this to turn ANY deployed AI system into a list of the articles it triggers, the
axes to measure, and the penalty range — the audit that finds exposure BEFORE we
contact the client.

Honesty: the crosswalk maps articles -> measurable axes; it does NOT invent a
verdict. Only a MEASURED axis (via the EUNOMIA engine) earns a number.
"""
from __future__ import annotations

# article -> (title, axis, requirement, max_penalty_class)
# classes: "market" (up to 3% / €15M), "high" (7% / €35M / prohibited), note
CROSSWALK = {
  "art1":  ("Scope",                          "governance", "Objects and scope; establishes the risk-based regime.", "—"),
  "art2":  ("Material scope",                 "governance", "Applies to providers/deployers of AI systems placed on the EU market.", "—"),
  "art3":  ("Definitions",                    "governance", "Definitions of AI system, provider, deployer, high-risk, etc.", "—"),
  "art5":  ("Prohibited practices",           "governance", "Banned: social scoring, subliminal manipulation, untargeted scraping, emotion inference (workplaces/schools), biometric categorisation.", "high/prohibited"),
  "art6":  ("High-risk classification",       "governance", "Annex III high-risk systems (critical infra, education, employment, essential services, law enforcement, migration, justice).", "high"),
  "art7":  ("High-risk amendment",            "governance", "Criteria for moving a system into/out of high-risk.", "high"),
  "art8":  ("Risk management system",         "care",       "Continuous risk management over the lifecycle.", "high"),
  "art9":  ("Data governance",                "provenance", "High-risk training/validation/test data: provenance, representativeness, bias.", "high"),
  "art10": ("Data governance detail",         "provenance", "Data quality, bias mitigation, sourcing and curation.", "high"),
  "art11": ("Technical documentation",        "conformance", "Documentation proving compliance (Annex IV).", "high"),
  "art12": ("Record keeping/automated logging","continuity", "Automated logs of operation for traceability.", "high"),
  "art13": ("Transparency/information",       "openness",   "Instructions for deployers; interpretation of outputs; capabilities/limits.", "high"),
  "art14": ("Human oversight",                "care",       "Natural persons able to override/stop the system; human-in-the-loop for high-risk.", "high"),
  "art15": ("Accuracy, robustness, cybersecurity","conformance", "Accuracy, resilience, robustness, cybersecurity standards.", "high"),
  "art16": ("Obligations of providers",       "governance", "Providers' obligations for high-risk systems.", "high"),
  "art17": ("Quality management system",      "conformance", "Provider QMS for high-risk systems.", "high"),
  "art18": ("Document retention",             "continuity", "Keep documentation 10 years after placing on market.", "high"),
  "art19": ("Correction/duty of information", "openness",   "Correct non-compliant systems + notify authorities/deployers.", "high"),
  "art20": ("Non-compliance corrective action","conformance", "Withdraw/recall/disable non-compliant systems.", "high"),
  "art21": ("Cooperation with authorities",   "governance", "Provide authorities the info needed to verify compliance.", "high"),
  "art22": ("Authorised representatives",     "governance", "Providers outside the EU must appoint an EU representative.", "high"),
  "art26": ("Obligations of deployers",       "governance", "Deployer duties: use per instructions, oversight, monitoring, logging.", "high"),
  "art27": ("Fundamental-rights impact assessment","care",  "Deployers of Annex III must assess fundamental-rights impact (public bodies).", "high"),
  "art40": ("Harmonised standards",           "conformance", "Compliance via harmonised standards.", "—"),
  "art43": ("Conformity assessment",          "conformance", "Ex-ante conformity assessment (Annexes VI/VII).", "high"),
  "art47": ("EU database",                    "openness",   "High-risk systems registered in the EU database.", "high"),
  "art50": ("Transparency obligations",       "provenance", "AI-generated content must be transparently marked (incl. deepfakes).", "market"),
  "art51": ("General-purpose AI (GPAI)","governance", "GPAI model obligations (Annex XI/XII).", "market"),
  "art52": ("GPAI systemic-risk models",      "care",       "GPAI with systemic risk: model evaluation, adversarial testing, reporting.", "market"),
  "art53": ("GPAI obligations",               "governance", "Technical docs, copyright policy, training-data summary.", "market"),
  "art54": ("GPAI systemic-risk obligations", "care",       "Systemic-risk evaluation, risk mitigation, incident reporting, cybersecurity.", "market"),
  "art55": ("GPAI codes of practice",         "conformance", "Codes of practice to support GPAI compliance.", "market"),
  "art73": ("Penalties (in general)",         "governance", "Member-state penalties for non-compliance.", "market"),
}

# Penalties per Reg (EU) 2024/1689 Art 99.
PENALTIES = {
  "market":  "up to €15M or 3% of global turnover",
  "high":    "up to €35M or 7% of global turnover (high-risk / prohibited)",
  "—":       "no direct penalty class; administrative measures",
}

AXIS_LABEL = {
  "governance": "risk-tier / prohibited vs permitted",
  "care":       "human-oversight adequacy",
  "provenance": "data governance / content transparency",
  "conformance": "documentation / QMS / accuracy-robustness",
  "openness":   "transparency / information to deployers",
  "continuity": "record-keeping / logging / retention",
}


def crosswalk(ai_system: str, domain_hints: list[str] | None = None) -> list[dict]:
    """Map an AI system to the EU AI Act articles it likely triggers.

    domain_hints: e.g. ["hiring", "credit", "critical-infra", "biometric"] narrows
    to the relevant Annex III high-risk areas. Returns the article exposure list.
    """
    high_risk_hint = any(domain_hints or []) and any(
        d in ("hiring", "employment", "education", "credit", "critical-infra", "law-enforcement",
              "migration", "justice", "biometric", "essential-services") for d in (domain_hints or []))
    out = []
    for art, (title, axis, req, cls) in CROSSWALK.items():
        # Always include the core governance + transparency + GPAI articles.
        if art in ("art5", "art6", "art8", "art9", "art11", "art13", "art14", "art15", "art50", "art51"):
            out.append(_row(art, title, axis, req, cls))
        elif high_risk_hint and art in ("art7", "art12", "art16", "art17", "art22", "art26", "art27", "art43", "art47"):
            out.append(_row(art, title, axis, req, cls))
    return out


def _row(art, title, axis, req, cls):
    return {"article": art, "title": title, "axis": axis,
            "axis_measure": AXIS_LABEL.get(axis, axis), "requirement": req,
            "exposure": PENALTIES.get(cls, "—"), "is_measured": axis in AXIS_LABEL}


if __name__ == "__main__":
    import json
    demo = crosswalk("AI credit-scoring for retail lending", ["credit"])
    print(json.dumps({"ai_system": "AI credit-scoring", "articles": demo, "n": len(demo)}, indent=2))
