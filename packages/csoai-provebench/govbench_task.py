# GovBench — EU AI Act risk-tier classification, graded deterministically.
#
# CSOAI (Council for the Safety of AI, UK) · https://csoai.org
#
# WHY THIS EXISTS
# Public LLM leaderboards measure capability. None of them measure whether a model can place an
# AI deployment in the right legal category under the EU AI Act — the judgement that decides
# whether a system is prohibited outright, needs a conformity assessment before EU placement,
# or merely carries transparency duties. Getting that wrong is not a style error; it is the
# difference between "ship it" and "Article 5 prohibited practice".
#
# HOW IT IS GRADED
# Deterministically. The model must answer with one bare tier token. A regex reads it, and an
# equality assertion decides. No model judges another model, so the same answer always scores
# the same, and the scoring code is auditable by anyone reading this file.
#
# WHY IT CANNOT BE GAMED BY GUESSING ONE ANSWER
# The item set is deliberately spread across all four tiers, including scenarios engineered to
# look severe but sit in a lower tier (a spam filter reading employee mail: employment context,
# but not an Annex III employment decision) and scenarios that look benign but are prohibited
# (a "wellness score" that is social scoring by another name). A model that answers PROHIBITED
# to everything scores 4/17; one that answers HIGH_RISK to everything scores 7/17. Both lose to
# reading the statute. That property is asserted by test_degenerate_strategies_lose() below,
# which runs offline and is the reason to trust the spread.
#
# REFUSALS COUNT AS WRONG, NOT AS MISSING
# A model that declines to classify has failed the task a compliance officer needed done. It is
# scored wrong and the transcript records the refusal — never silently dropped, which would
# flatter the model by shrinking its denominator.

import re

import kaggle_benchmarks as kbench

TIERS = ("PROHIBITED", "HIGH_RISK", "LIMITED_RISK", "MINIMAL_RISK")

INSTRUCTION = (
    "You are classifying an AI system under Regulation (EU) 2024/1689 (the EU AI Act).\n"
    "Reply with EXACTLY ONE of these tokens and nothing else — no punctuation, no explanation:\n"
    "PROHIBITED | HIGH_RISK | LIMITED_RISK | MINIMAL_RISK\n\n"
    "PROHIBITED   = an Article 5 prohibited practice.\n"
    "HIGH_RISK    = Annex III high-risk, or a safety component under Article 6(1).\n"
    "LIMITED_RISK = not high-risk, but Article 50 transparency duties apply (the system\n"
    "               interacts with people, or generates/manipulates content).\n"
    "MINIMAL_RISK = none of the above.\n\n"
    "Scenario: "
)


# Tier written any way a model plausibly writes it: HIGH_RISK, HIGH-RISK, "high risk".
# Built against the RAW text — an earlier version normalised spaces to underscores, which broke
# \b (underscore is a word character), so "The answer is PROHIBITED." read as no answer at all
# and a model replying in a sentence was scored as having refused. Caught by the case below.
_TIER_RX = {t: re.compile(rf"\b{t.replace('_', '[ _-]?')}\b", re.I) for t in TIERS}


def _extract_tier(text: str) -> str:
    """First tier the reply commits to, or '' if it never names one.

    First-token-wins: for a compliant answer the token IS the whole reply, and for a chatty one
    the leading verdict is the answer. '' means the model named no tier — scored wrong, because
    a compliance officer asked a question and got nothing usable back.
    """
    hits = [(m.start(), t) for t, rx in _TIER_RX.items() if (m := rx.search(text))]
    return min(hits)[1] if hits else ""


@kbench.task(
    name="GovBench — EU AI Act risk tier",
    description=(
        "Classify an AI deployment scenario into its EU AI Act risk tier "
        "(PROHIBITED / HIGH_RISK / LIMITED_RISK / MINIMAL_RISK). Deterministic grading against "
        "statute-anchored ground truth. By CSOAI — csoai.org"
    ),
    version=1,
)
def govbench_tier(llm, scenario: str, expected: str, anchor: str) -> None:
    reply = llm.prompt(INSTRUCTION + scenario)
    got = _extract_tier(reply)

    # A provider that returns an EMPTY string has not answered — it has been filtered or


    # has failed. Scoring that as a WRONG ANSWER is a measurement error: it punishes the


    # most safety-trained models hardest, because they are the ones whose output gets


    # blocked. Observed live: 12 of 15 empty replies across 2,468 runs came from a single


    # frontier model, costing it 13 points of apparent accuracy it had not actually lost.


    # Tagged PROVIDER_EMPTY so the board can exclude it rather than silently miscount it.


    _tag = "PROVIDER_EMPTY" if reply.strip() == "" else ""


    kbench.assertions.assert_true(
        got != "",
        expectation=(
            f"Model commits to a tier for: {scenario[:70]}… "
            f"{_tag} (reply began: {reply[:60]!r})"
        ),
    )
    kbench.assertions.assert_equal(
        expected,
        got,
        expectation=f"{anchor} — expected {expected} for: {scenario[:70]}…",
    )


# ── The item set ──────────────────────────────────────────────────────────────────────────
# Each row carries the statutory anchor that makes the answer defensible. Anchors are the
# ground for the label; a disputed row should be argued against its anchor, not against taste.
ITEMS = [
    # PROHIBITED — Article 5
    ("A government platform scores citizens on trustworthiness using unrelated social behaviour, "
     "and the score restricts access to public services.",
     "PROHIBITED", "Art 5(1)(c) social scoring"),
    ("A wellness app assigns each employee a 'community contribution score' from their social "
     "media and off-duty behaviour; low scores reduce access to company benefits.",
     "PROHIBITED", "Art 5(1)(c) social scoring — benign framing, same practice"),
    ("A retailer scrapes CCTV and public webcam feeds to build a facial recognition database "
     "with no targeting criteria.",
     "PROHIBITED", "Art 5(1)(e) untargeted facial scraping"),
    ("Police run live facial recognition on a public square to identify anyone on a watchlist, "
     "with no judicial authorisation and no imminent threat.",
     "PROHIBITED", "Art 5(1)(h) real-time remote biometric ID in public"),

    # HIGH_RISK — Annex III
    ("An AI ranks job applicants and filters CVs before any human sees them.",
     "HIGH_RISK", "Annex III 4(a) employment — recruitment"),
    ("A hospital deploys a triage model that orders emergency patients by urgency.",
     "HIGH_RISK", "Annex III 5(a) essential services / emergency triage"),
    ("A bank uses a model to decide consumer creditworthiness for mortgage applications.",
     "HIGH_RISK", "Annex III 5(b) creditworthiness"),
    ("A university admissions system scores applicants and determines who is admitted.",
     "HIGH_RISK", "Annex III 3(a) education access"),
    ("A model assesses asylum applications and recommends grant or refusal to caseworkers.",
     "HIGH_RISK", "Annex III 7 migration and asylum"),
    ("An AI component controls pressure regulation in a municipal drinking-water network.",
     "HIGH_RISK", "Annex III 2 critical infrastructure safety component"),
    ("An insurer uses AI for risk assessment and pricing of life and health insurance.",
     "HIGH_RISK", "Annex III 5(c) life/health insurance risk assessment"),

    # LIMITED_RISK — Article 50
    ("A retail website runs a customer-service chatbot that answers questions about orders.",
     "LIMITED_RISK", "Art 50(1) disclosure that the user interacts with an AI"),
    ("A marketing tool generates photorealistic images of people for ad campaigns.",
     "LIMITED_RISK", "Art 50(2) synthetic content marking"),
    ("A newsroom tool produces synthetic voice-overs of presenters reading published articles.",
     "LIMITED_RISK", "Art 50(4) deep fake / synthetic audio disclosure"),

    # MINIMAL_RISK — deliberately adjacent to higher tiers
    ("A spam filter classifies inbound email for a company's staff mailboxes.",
     "MINIMAL_RISK", "No Annex III use case — employment context but not an employment decision"),
    ("A warehouse uses AI to optimise pallet placement and forklift routing for throughput.",
     "MINIMAL_RISK", "Industrial optimisation, no Annex III category, no safety component"),
    ("A video game uses AI to adapt enemy difficulty to the player's skill.",
     "MINIMAL_RISK", "Recital ic — AI in video games, minimal risk"),

    # ── Discriminating set ────────────────────────────────────────────────────────────────
    # Added at v2 because v1 was answered 17/17 by the first frontier model tested: a benchmark
    # every model aces measures nothing. These turn on provisions that are easy to miss —
    # the Art 6(3) derogations, the Art 5 practices people forget exist, and the two routes
    # into high-risk that are NOT Annex III. Each still has one defensible answer.
    ("Software flags CVs containing keywords and forwards them to a recruiter, who reads every "
     "CV in full regardless and makes all decisions. It performs a narrow procedural task and "
     "does not materially influence the outcome.",
     "MINIMAL_RISK", "Art 6(3)(a) derogation — narrow procedural task, no material influence"),
    ("A call-centre tool infers the emotional state of employees from their voice during calls "
     "and reports it to their managers.",
     "PROHIBITED", "Art 5(1)(f) emotion inference in the workplace"),
    ("A security product categorises people from facial images to infer their ethnicity and "
     "political orientation.",
     "PROHIBITED", "Art 5(1)(g) biometric categorisation inferring protected attributes"),
    ("An AI is the safety component of a surgical robot, and that robot needs third-party "
     "conformity assessment under the Medical Devices Regulation.",
     "HIGH_RISK", "Art 6(1) — safety component of a regulated product; NOT via Annex III"),
    ("A model is developed and used solely for scientific research and is never placed on the "
     "market or put into service.",
     "MINIMAL_RISK", "Art 2(6) — scientific research and development is out of scope"),
    ("An AI profiles which residents of a city are likely to commit a crime, based purely on "
     "personality traits and background, with no link to objective verifiable facts.",
     "PROHIBITED", "Art 5(1)(d) predictive policing on profiling alone"),
    ("A model that detects manufacturing defects on a bottling line is used to route faulty "
     "bottles to a reject bin. No person is assessed and no regulated product safety function "
     "depends on it.",
     "MINIMAL_RISK", "Industrial QC — no Annex III use, not an Art 6(1) safety component"),
]


# ── Offline self-checks — the anti-gaming guarantee, verifiable without any model ─────────
def test_degenerate_strategies_lose() -> None:
    """A single-answer strategy must lose to reading the statute.

    Published as part of the task so the spread is auditable rather than asserted. If a future
    edit skews the item set toward one tier, this fails and the benchmark stops being honest.
    """
    n = len(ITEMS)
    for tier in TIERS:
        score = sum(1 for _, exp, _ in ITEMS if exp == tier)
        assert score / n < 0.5, f"always-{tier} scores {score}/{n} — item set is skewed"


def test_extractor_is_strict() -> None:
    assert _extract_tier("HIGH_RISK") == "HIGH_RISK"
    assert _extract_tier("high-risk") == "HIGH_RISK"
    assert _extract_tier("minimal risk") == "MINIMAL_RISK"
    assert _extract_tier("I cannot help with that.") == ""     # refusal -> no tier -> wrong
    assert _extract_tier("As an AI I won't classify this.") == ""
    assert _extract_tier("MINIMAL_RISK, not HIGH_RISK") == "MINIMAL_RISK"  # first token wins
    # Regression: a sentence answer must still count. An earlier normalisation mapped spaces to
    # underscores, which killed \b (underscore is a word char) and scored this as a refusal —
    # silently punishing every model that answers in prose rather than a bare token.
    assert _extract_tier("The answer is PROHIBITED.") == "PROHIBITED"
    assert _extract_tier("This is high risk under Annex III.") == "HIGH_RISK"


test_degenerate_strategies_lose()
test_extractor_is_strict()

# ── Run every item against the model under test ───────────────────────────────────────────
import pandas as pd  # noqa: E402  (kept below the offline checks so they run even if absent)

evaluation_data = pd.DataFrame(
    [{"scenario": s, "expected": e, "anchor": a} for s, e, a in ITEMS]
)

govbench_tier.evaluate(
    llm=[kbench.llm],
    evaluation_data=evaluation_data,
    n_jobs=4,
    timeout=180,
)
