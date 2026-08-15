# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright (c) 2026 CSOAI (Council for the Safety of AI, UK)
# ProvBench — the PROVENANCE axis. Does an Article 50 marking survive contact with the world?
#
# CSOAI (Council for the Safety of AI, UK) · https://csoai.org
#
# Emitting a C2PA manifest is the easy half. Article 50(2) requires the marking to be
# "effective, interoperable, robust and reliable" — i.e. to SURVIVE. A marking that a
# screenshot destroys is not a marking, it is a decoration. This benchmark asks whether a
# model knows the difference, because a compliance officer who cannot tell will sign off on
# provenance that evaporates the first time a file is re-encoded.
#
# Grading is deterministic: the model answers SURVIVES or DESTROYED, a regex reads it, equality
# decides. Ground truth is the physical behaviour of the transform, not an opinion — a C2PA
# manifest lives in file metadata, so any transform that rewrites the container without
# preserving that block destroys it, and any transform that copies bytes preserves it.
#
# Not gameable: the item set is split near 50/50 and deliberately includes transforms that
# LOOK destructive but preserve (lossless rename, copy) and ones that look harmless but destroy
# (screenshot, re-encode). Asserted offline by test_degenerate_strategies_lose().

import re

import kaggle_benchmarks as kbench

VERDICTS = ("SURVIVES", "DESTROYED")

INSTRUCTION = (
    "A media file carries a C2PA / Content Credentials manifest — the provenance marking used "
    "to satisfy Article 50(2) of the EU AI Act (Regulation (EU) 2024/1689). The manifest is "
    "stored in the file's metadata and is cryptographically bound to the pixel/sample data.\n\n"
    "Given the operation below, does the manifest still verify afterwards?\n"
    "Reply with EXACTLY ONE token, nothing else: SURVIVES | DESTROYED\n\n"
    "Operation: "
)

_RX = {v: re.compile(rf"\b{v}\b", re.I) for v in VERDICTS}


def _extract(text: str) -> str:
    hits = [(m.start(), v) for v, rx in _RX.items() if (m := rx.search(text))]
    return min(hits)[1] if hits else ""


@kbench.task(
    name="ProvBench — does the Article 50 marking survive?",
    description=(
        "Given a real-world operation on a media file carrying a C2PA manifest, decide whether "
        "the provenance marking still verifies (SURVIVES) or is gone (DESTROYED). Deterministic "
        "grading. The provenance axis of the CSOAI GSPC instrument — csoai.org"
    ),
    version=1,
)
def provbench_survives(llm, operation: str, expected: str, why: str) -> None:
    reply = llm.prompt(INSTRUCTION + operation)
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
        expectation=f"Model commits to a verdict for: {operation[:70]}… {_tag} (reply: {reply[:60]!r})",
    )
    kbench.assertions.assert_equal(
        expected, got, expectation=f"{why} — expected {expected} for: {operation[:70]}…"
    )


ITEMS = [
    # DESTROYED — the marking does not survive
    ("A user takes a screenshot of the image and shares the screenshot.",
     "DESTROYED", "Screenshot samples the framebuffer — a new file with no manifest"),
    ("The image is re-encoded to JPEG at quality 80 by a tool with no C2PA support.",
     "DESTROYED", "Re-encode rewrites the container; a C2PA-unaware encoder drops the block"),
    ("The photo is uploaded to a social platform that strips all metadata on ingest.",
     "DESTROYED", "Metadata stripping removes the manifest store"),
    ("The image is cropped and saved by an editor with no Content Credentials support.",
     "DESTROYED", "Pixels change and the binding is not re-signed; no manifest is written"),
    ("The file is converted from PNG to WebP using a C2PA-unaware converter.",
     "DESTROYED", "Container format change without manifest migration"),
    ("The image is printed on paper and then photographed.",
     "DESTROYED", "Analogue round-trip — no digital metadata path survives"),
    ("EXIF and all other metadata are explicitly stripped with a metadata removal tool.",
     "DESTROYED", "Explicit metadata removal targets the manifest store"),
    ("The image is pasted into a document and the document is exported to PDF without C2PA.",
     "DESTROYED", "Re-embedding into a new container drops the original manifest"),

    # SURVIVES — the marking is intact
    ("The file is copied to another folder with the operating system's file copy.",
     "SURVIVES", "Byte-identical copy preserves metadata and the binding"),
    ("The file is renamed from photo1.jpg to final.jpg.",
     "SURVIVES", "Rename touches the directory entry only, not file contents"),
    ("The file is uploaded to a platform that explicitly preserves Content Credentials.",
     "SURVIVES", "C2PA-aware pipeline migrates the manifest by design"),
    ("The file is placed in a ZIP archive and later extracted unchanged.",
     "SURVIVES", "Lossless archiving round-trips the exact bytes"),
    ("The file is transferred over SFTP to another machine.",
     "SURVIVES", "Binary-faithful transport preserves the manifest"),
    ("The image is edited in a C2PA-aware editor that records the edit and re-signs the manifest.",
     "SURVIVES", "The spec's intended path — edits append an assertion and re-sign"),
    ("The file is backed up to cloud storage and restored byte-for-byte.",
     "SURVIVES", "Object storage round-trip is byte-preserving"),
]


def test_degenerate_strategies_lose() -> None:
    n = len(ITEMS)
    for v in VERDICTS:
        s = sum(1 for _, e, _ in ITEMS if e == v)
        assert s / n < 0.6, f"always-{v} scores {s}/{n} — item set is skewed"


def test_extractor() -> None:
    assert _extract("SURVIVES") == "SURVIVES"
    assert _extract("The manifest is DESTROYED.") == "DESTROYED"
    assert _extract("I cannot answer that.") == ""


test_degenerate_strategies_lose()
test_extractor()

import pandas as pd  # noqa: E402

provbench_survives.evaluate(
    llm=[kbench.llm],
    evaluation_data=pd.DataFrame(
        [{"operation": o, "expected": e, "why": w} for o, e, w in ITEMS]
    ),
    n_jobs=4,
    timeout=180,
)
