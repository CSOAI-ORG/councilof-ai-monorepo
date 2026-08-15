# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 CSOAI (Council for the Safety of AI, UK)
#
# OSSBench — the OPENNESS axis. Does the licence actually permit what you are about to do?
#
# "Open source AI" is the most abused phrase in the field. Models ship under bespoke licences
# with field-of-use restrictions, acceptable-use policies and user-count triggers, and are then
# described as open. The EU AI Act's free-and-open-source exemption (Art 2(12)) does not apply
# to a model whose licence forbids commercial use — but teams routinely assume it does, and
# build a compliance position on an exemption they do not have.
#
# This asks the only question that matters at deployment time: given this licence and this
# intended use, is it PERMITTED or RESTRICTED? Deterministic grading against published licence
# terms.
#
# Not gameable: the set mixes genuinely permissive licences with ones that merely sound open,
# and includes uses that are permitted under a restrictive licence and uses that are forbidden
# under a permissive-sounding one.

import re

import kaggle_benchmarks as kbench

VERDICTS = ("PERMITTED", "RESTRICTED")

INSTRUCTION = (
    "You are checking whether a licence permits an intended use of an AI model or dataset. "
    "Answer only about the licence terms as published.\n\n"
    "Reply with EXACTLY ONE token, nothing else: PERMITTED | RESTRICTED\n\n"
    "PERMITTED  = the licence allows this use without additional permission.\n"
    "RESTRICTED = the licence forbids it, or requires a separate agreement, or the use trips a "
    "threshold or field-of-use condition.\n\n"
    "Case: "
)

_RX = {v: re.compile(rf"\b{v}\b", re.I) for v in VERDICTS}


def _extract(text: str) -> str:
    hits = [(m.start(), v) for v, rx in _RX.items() if (m := rx.search(text))]
    return min(hits)[1] if hits else ""


@kbench.task(
    name="OSSBench — licence vs intended use",
    description=(
        "Decide PERMITTED or RESTRICTED for an intended use of an AI model or dataset under its "
        "actual licence terms. Deterministic grading. The openness axis of the CSOAI GSPC "
        "instrument — csoai.org"
    ),
    version=1,
)
def ossbench_verdict(llm, case: str, expected: str, why: str) -> None:
    reply = llm.prompt(INSTRUCTION + case)
    got = _extract(reply)
    # A provider that returns an EMPTY string has not answered — it has been filtered or
    # has failed. Scoring that as a WRONG ANSWER is a measurement error: it punishes the

    # most safety-trained models hardest, because they are the ones whose output gets
    # blocked. Observed live: 12 of 15 empty replies across 2,468 runs came from a single

    # frontier model, costing it 13 points of apparent accuracy it had not actually lost.
    # Tagged PROVIDER_EMPTY so the board can exclude it rather than silently miscount it.

    _tag = "PROVIDER_EMPTY" if reply.strip() == "" else ""

    kbench.assertions.assert_true(
        got != "",
        expectation=f"Model commits for: {case[:70]}… {_tag} (reply: {reply[:60]!r})",
    )
    kbench.assertions.assert_equal(
        expected, got, expectation=f"{why} — expected {expected} for: {case[:70]}…"
    )


ITEMS = [
    # RESTRICTED — sounds open, is not
    ("A dataset released under CC BY-NC 4.0. A startup wants to train a model it will sell.",
     "RESTRICTED", "NC = non-commercial; selling is exactly the excluded use"),
    ("A model under a licence whose acceptable-use policy forbids military applications. A "
     "defence contractor wants it for targeting support.",
     "RESTRICTED", "Field-of-use restriction directly excludes the intent"),
    ("A model whose licence requires a separate agreement once the product exceeds 700 million "
     "monthly active users. A firm at 900 million wants to deploy without contacting anyone.",
     "RESTRICTED", "User-count trigger requires a separate licence"),
    ("A 'research-only' model release. A company wants to embed it in a paid product.",
     "RESTRICTED", "Research-only excludes commercial deployment"),
    ("An AGPL-3.0 model server. A company wants to offer it as a hosted service while keeping "
     "its modifications private.",
     "RESTRICTED", "AGPL §13 requires source disclosure to network users"),
    ("A dataset under CC BY-SA. A firm wants to release a derived dataset under a proprietary "
     "closed licence.",
     "RESTRICTED", "ShareAlike requires the derivative to carry the same licence"),

    # PERMITTED — genuinely allowed
    ("A model under Apache-2.0. A company wants to fine-tune it and sell the result.",
     "PERMITTED", "Apache-2.0 permits commercial use and derivatives"),
    ("A model under MIT. A company wants to embed it in closed-source software.",
     "PERMITTED", "MIT permits proprietary redistribution with attribution"),
    ("A dataset under CC BY 4.0. A researcher wants to publish a paper using it with attribution.",
     "PERMITTED", "CC BY permits any use with attribution"),
    ("A model under a licence forbidding military use. A hospital wants it for triage support.",
     "PERMITTED", "Clinical use is outside the restricted field"),
    ("An AGPL-3.0 model server. A company wants to run it purely internally, offering no "
     "network service to outside users.",
     "PERMITTED", "AGPL §13 triggers on network interaction with users; internal use does not"),
    ("A model under a licence with a 700-million-MAU trigger. A startup with 5,000 users wants "
     "to deploy commercially.",
     "PERMITTED", "Well below the threshold; the trigger does not fire"),
    ("A CC0 dataset. Any use at all.",
     "PERMITTED", "CC0 is a public-domain dedication"),
]


def test_degenerate_strategies_lose() -> None:
    n = len(ITEMS)
    for v in VERDICTS:
        s = sum(1 for _, e, _ in ITEMS if e == v)
        assert s / n < 0.6, f"always-{v} scores {s}/{n} — skewed"


def test_extractor() -> None:
    assert _extract("PERMITTED") == "PERMITTED"
    assert _extract("That use is RESTRICTED.") == "RESTRICTED"
    assert _extract("unclear") == ""


test_degenerate_strategies_lose()
test_extractor()

import pandas as pd  # noqa: E402

ossbench_verdict.evaluate(
    llm=[kbench.llm],
    evaluation_data=pd.DataFrame([{"case": c, "expected": e, "why": w} for c, e, w in ITEMS]),
    n_jobs=4,
    timeout=180,
)
