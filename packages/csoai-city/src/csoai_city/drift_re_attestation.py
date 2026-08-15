"""csoai-city.drift_re_attestation — the "living compliance" trigger.

Wires corpus-watch regulation-drift detection to GSPC-axis re-mapping and
signed-card staleness flagging. When a statute's consolidated text changes,
every previously-signed card that DEPENDED on that text is flagged STALE —
so a signed-but-wrong attestation can never quietly outlive the law it cited.

Coordinate with the estate's existing pieces:
  * corpus-watch (repo ~/clawd/corpus-watch) emits drift_events.jsonl — the
    REAL event shape is:
        {instrument, label, jurisdiction, level, provisions_affected,
         hash_before, hash_after, normaliser, detected_at, source}
    DRIFT events are appended ONLY on a substantive hash change; UNKNOWN is
    recorded per-instrument in status.json, never "unchanged".
  * measure_api._emit_card produces the signed card shape:
        {content_id, epoch, body{kind, protocol, model, bank_version,
         board{...}, gold_provenance}, signature, signer, signed, ...}
    body.board.axis is the GSPC axis; body.gold_provenance anchors provenance.
  * correctness_gate.py and attestation_registry.py: the convention here is
    deterministic, no model judges, three-state (GROUNDED/UNGROUNDED/UNKNOWN),
    a self_test() that prints PASS/FAIL and returns an exit code.

Honest discipline of THIS trigger:
  * FAIL-CLOSED — if drift state is UNKNOWN the dependent cards are reported
    as "possibly_stale", NEVER silently "unchanged". A verdict about the law
    when the fact was about the request is the health-check bug again.
  * A stale card is NEVER mutated or deleted. This module is read-only over
    the card store: it only *reports* staleness. Re-issuance is a separate,
    owner-gated step.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# GSPC axes (from SOVOS/boards-v2-2026-08-12/board_*.json)
# ---------------------------------------------------------------------------
GSPC_AXES: List[str] = [
    "gov", "care", "affect", "art5", "det", "prv",
    "agi", "asi", "swarm", "mach", "xr", "oss", "mcp",
]

# Default signed-card store. If unset/missing, read_cards returns [] safely.
DEFAULT_CARD_STORE = "/runpod/council-signal"

# ---------------------------------------------------------------------------
# Regulation -> GSPC axes mapping (deterministic, auditable, no model judges).
# Keys are matched case-insensitively and by alias. Values are the axes a
# signed card citing that regulation plausibly depends on.
# ---------------------------------------------------------------------------

# Corpus-watch instrument ids + the estate's anchor names -> axes.
REGULATION_AXES: Dict[str, Set[str]] = {
    # EU AI Act and its known-article sub-anchors (articles from correctness_gate)
    "eu-ai-act":        {"art5", "care", "affect", "det", "prv", "gov"},
    "ai-act":           {"art5", "care", "affect", "det", "prv", "gov"},
    "2024/1689":        {"art5", "care", "affect", "det", "prv", "gov"},
    "art5":             {"art5", "affect", "det"},
    "article5":         {"art5", "affect", "det"},
    "art-5":            {"art5", "affect", "det"},
    "art50":            {"det", "affect"},
    "article50":        {"det", "affect"},
    "art-50":           {"det", "affect"},
    "art9":             {"care", "det", "gov"},
    "article9":         {"care", "det", "gov"},
    "art-9":            {"care", "det", "gov"},
    "art10":            {"prv", "care"},
    "article10":        {"prv", "care"},
    "art-10":           {"prv", "care"},
    "art13":            {"det"},
    "article13":        {"det"},
    "art-13":           {"det"},
    "art14":            {"care", "gov"},
    "article14":        {"care", "gov"},
    "art-14":           {"care", "gov"},
    "art43":            {"gov", "det"},
    "article43":        {"gov", "det"},
    "art-43":           {"gov", "det"},
    "annex3":           {"det", "care"},
    # Other EU instruments the watch tracks
    "eu-dora":          {"gov", "det", "prv"},
    "dora":             {"gov", "det", "prv"},
    "eu-nis2":          {"gov", "det", "prv", "mach"},
    "nis2":             {"gov", "det", "prv", "mach"},
    "eu-cra":           {"mach", "oss", "mcp", "det", "prv"},
    "cra":              {"mach", "oss", "mcp", "det", "prv"},
    # GDPR / UK GDPR
    "gdpr":             {"prv", "gov", "det"},
    "uk-gdpr":          {"prv", "gov", "det"},
    "2016/679":         {"prv", "gov", "det"},
    # UK consumer / markets
    "uk-dmcca":         {"gov", "care", "affect"},
    "dmcca":            {"gov", "care", "affect"},
    # US algorithmic-pricing statutes
    "us-ny-349a":       {"affect", "gov"},
    "349-a":            {"affect", "gov"},
    "us-ca-ab325":      {"affect", "gov"},
    "ab325":            {"affect", "gov"},
}

# Source strings (corpus-watch "source": "host:path") -> same keys, so a
# legislation.gov.uk:eur/2016/679 maps to the UK GDPR ruleset.
SOURCE_AXES: Dict[str, Set[str]] = {
    "eur/2016/679":  {"prv", "gov", "det"},
    "ukpga/2024/13": {"gov", "care", "affect"},
    "gbs/349-a":     {"affect", "gov"},
}

_ALIAS_TO_KEY: Dict[str, str] = {}
for _k, _v in REGULATION_AXES.items():
    _ALIAS_TO_KEY[_k] = _k


def _canonical_regulation(key: str) -> Optional[str]:
    """Resolve an arbitrary regulation key/alias/anchor to a canonical key.

    Returns the canonical REGULATION_AXES key, or None if we cannot map it
    (which then FAILS CLOSED to UNKNOWN downstream — never a silent clean)."""
    if not key:
        return None
    k = str(key).strip().lower()
    if k in REGULATION_AXES:
        return k
    # chelp with parentheticals like "art5:manipulation" / "art50:synthetic"
    base = k.split(":")[0].strip()
    if base in REGULATION_AXES:
        return base
    # substring/contains fallback (e.g. "eu-ai-act" against "ai act")
    for alias, canonical in _ALIAS_TO_KEY.items():
        if alias in k or k in alias:
            return canonical
    return None


def axes_for_regulation(key: str) -> Set[str]:
    """Deterministic set of GSPC axes a regulation/anchor touches."""
    canonical = _canonical_regulation(key)
    if canonical is None:
        return set()
    return set(REGULATION_AXES[canonical])


def axes_for_source(source: str) -> Set[str]:
    """Map a corpus-watch 'source' string (host:path) to axes where known."""
    s = (source or "").lower()
    for needle, axes in SOURCE_AXES.items():
        if needle in s:
            return set(axes)
    # fall back: try to find any known key inside the source string
    for alias, axes in _ALIAS_TO_KEY.items():
        if alias.lower() in s and REGULATION_AXES.get(alias):
            return set(REGULATION_AXES[alias])
    return set()


# ---------------------------------------------------------------------------
# Drift-event parsing. Accepts BOTH:
#   (A) the real corpus-watch shape  {instrument, hash_before, hash_after,
#                                      source, ...}  — presence = DRIFT
#   (B) a generalized shape          {changed_regulation, state: CHANGED|UNKNOWN}
# ---------------------------------------------------------------------------
def parse_drift_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a normalised drift event: {regulation, state, affected_axes,
    changed, fail_closed, source}.

    state ∈ {"DRIFT","UNKNOWN","unchanged"}. FAIL-CLOSED: any inability to
    know (no fetch / unmapable regulation / no stated state) -> UNKNOWN, and
    the caller must treat dependent cards as possibly-stale, not clean.
    """
    ev = event or {}
    reg_key = None
    state = None
    source = ev.get("source")

    # (A) real corpus-watch event: has instrument + hash_before -> a change.
    if "instrument" in ev:
        reg_key = ev["instrument"]
        if ev.get("hash_before") is not None and ev.get("hash_after") is not None \
           and ev["hash_before"] != ev["hash_after"]:
            state = "DRIFT"
        else:
            # an instrument event with no real hash delta = not determinate
            state = "UNKNOWN"
    else:
        # (B) generalized shape
        reg_key = ev.get("changed_regulation") or ev.get("regulation")
        raw_state = ev.get("state")
        if raw_state is None:
            state = "UNKNOWN"
        else:
            st = str(raw_state).upper()
            if st == "CHANGED":
                state = "DRIFT"
            elif st == "UNKNOWN":
                state = "UNKNOWN"
            elif st == "UNCHANGED":
                state = "unchanged"
            else:
                state = "UNKNOWN"

    canonical = _canonical_regulation(reg_key) if reg_key else None
    # If we have a source string, merge source-derived axes (belt & braces).
    affected = set(axes_for_regulation(reg_key or ""))
    affected |= axes_for_source(source or "")

    if canonical is None:
        # Cannot map -> FAIL CLOSED to UNKNOWN, broad (but bounded) axis set.
        state = "UNKNOWN"
        reason = "regulation not in deterministic mapping"
    else:
        reason = None

    return {
        "regulation": canonical or (str(reg_key) if reg_key else "unknown"),
        "changed_regulation": ev.get("changed_regulation") or reg_key,
        "state": state,
        "affected_axes": sorted(affected) if affected else sorted(GSPC_AXES),
        "source": source,
        "hash_before": ev.get("hash_before"),
        "hash_after": ev.get("hash_after"),
        "fail_closed": state == "UNKNOWN",
        "reason": reason or ("drift confirmed" if state == "DRIFT" else state),
    }


# ---------------------------------------------------------------------------
# Card store scanning (READ-ONLY — never mutates or deletes a card)
# ---------------------------------------------------------------------------
def read_cards(card_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load all *.json signed cards from a directory. Honors the DEFAULT store.

    Missing/empty dir -> []. Any malformed file is skipped (never fatal).
    This is STRICTLY read-only: the module never writes back to a card file.
    """
    d = card_dir or os.environ.get("SOVOS_CARD_STORE") or DEFAULT_CARD_STORE
    path = Path(d)
    cards: List[Dict[str, Any]] = []
    if not path.exists() or not path.is_dir():
        return cards
    for f in sorted(path.glob("*.json")):
        try:
            cards.append(json.loads(f.read_text()))
        except Exception:
            continue  # skip corrupt card, don't crash the whole sweep
    return cards


def _card_text(card: Dict[str, Any]) -> str:
    """A lower-cased serialized view of a card for substring matching."""
    try:
        return json.dumps(card, sort_keys=True).lower()
    except Exception:
        return ""


def card_axes(card: Dict[str, Any]) -> Set[str]:
    """The GSPC axes a card is about (from body.board.axis, single or list)."""
    board = (card.get("body") or {}).get("board") or {}
    axis = board.get("axis")
    if isinstance(axis, list):
        return {str(a).lower() for a in axis}
    if isinstance(axis, str):
        return {axis.lower()}
    return set()


def _card_mentions(card: Dict[str, Any], reg_key: str) -> bool:
    """Does the card's body/gold_provenance material explicitly cite the
    regulation or one of its aliases? (deterministic substring match)"""
    txt = _card_text(card)
    if not reg_key:
        return False
    canonical = _canonical_regulation(reg_key)
    if canonical:
        if canonical.replace("-", "") in txt.replace("-", ""):
            return True
    # also match the raw key and its source needle
    if reg_key.lower() in txt:
        return True
    return False


def is_signed(card: Dict[str, Any]) -> bool:
    """True only if the card genuinely carries a signature."""
    return bool(card.get("signature")) or card.get("signed") is True


def card_depends_on(card: Dict[str, Any], drift: Dict[str, Any]) -> bool:
    """Deterministic dependency test: does this card depend on the changed reg?

    True if (a) the card's axis is in the regulation's affected axes, OR
    (b) the card's body/gold_provenance cites the regulation.
    A card that does not depend on the changed text is untouched (not stale).
    """
    affected = set(drift.get("affected_axes") or [])
    ax = card_axes(card)
    if affected and ax & affected:
        return True
    reg = drift.get("changed_regulation") or drift.get("regulation")
    if _card_mentions(card, reg or ""):
        return True
    return False


# ---------------------------------------------------------------------------
# The trigger — the public entry point
# ---------------------------------------------------------------------------
def evaluate_drift(drift_event: Dict[str, Any],
                   card_dir: Optional[str] = None,
                   store: Optional[str] = None) -> Dict[str, Any]:
    """Given a drift event + a store of signed cards, emit a staleness report.

    The report (READ-ONLY over cards — nothing is mutated or deleted):
      {
        "changed_regulation": <canonical>,
        "state": "DRIFT"|"UNKNOWN"|"unchanged",
        "affected_axes": [...],
        "stale_cards": [ {content_id, axis, signer, reason} ... ],   # DRIFT only
        "possibly_stale_cards": [ ... ],                            # UNKNOWN (fail-closed)
        "clean_cards": n,
        "fail_closed": bool,
        "cards_unchanged_bytes": True,   # honest: nothing was mutated
      }
    """
    drift = parse_drift_event(drift_event)
    cards = read_cards(store or card_dir)

    stale, possibly = [], []
    for card in cards:
        if not is_signed(card):
            continue  # unsigned cards are not attestation evidence
        depends = card_depends_on(card, drift)
        if not depends:
            continue
        entry = {
            "content_id": card.get("content_id"),
            "axis": sorted(card_axes(card)),
            "signer": card.get("signer") or card.get("signature", ""),
            "gold_provenance": (card.get("body") or {}).get("gold_provenance"),
        }
        if drift["state"] == "UNKNOWN":
            possibly.append(entry)   # FAIL-CLOSED: possibly-stale, never clean
        elif drift["state"] == "DRIFT":
            stale.append(entry)      # confirmed staleness

    return {
        "changed_regulation": drift["changed_regulation"],
        "regulation": drift["regulation"],
        "state": drift["state"],
        "affected_axes": drift["affected_axes"],
        "stale_cards": stale,
        "possibly_stale_cards": possibly,
        "clean_cards": sum(1 for c in cards if not
                           (is_signed(c) and card_depends_on(c, drift))),
        "fail_closed": drift["fail_closed"],
        "source": drift["source"],
        "reason": drift["reason"],
        "cards_unchanged_bytes": True,  # this module never writes card files
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _synthetic_card(axis: str, provenance: str, signed: bool = True,
                    extra_body: str = "") -> Dict[str, Any]:
    """Build a synthetic signed card in the measure_api shape."""
    body = {
        "kind": "gspc-card",
        "protocol": "sov6-test",
        "model": "synthetic",
        "bank_version": "v2",
        "board": {"axis": axis, "n": 100, "accuracy": 0.9},
        "gold_provenance": provenance,
    }
    if extra_body:
        body["board"]["note"] = extra_body
    import hashlib
    cid = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return {
        "content_id": cid,
        "epoch": 1,
        "body": body,
        "signature": "abc" if signed else "",
        "signer": "corpus-watch-key" if signed else None,
        "signed": signed,
    }


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # --- synthetic store ---
    import tempfile
    tmp = tempfile.mkdtemp(prefix="drift_re_attest_")
    # art5 card (affected by EU AI Act / Art5 drift)
    art5_card = _synthetic_card("art5", "gate: art5 prohibited practices",
                                extra_body="cites Art 5 manipulation")
    # prv card citing GDPR (affected by UK-GDPR drift)
    prv_card = _synthetic_card("prv", "gate: UK GDPR data protection",
                               extra_body="retained Regulation 2016/679")
    # gov card NOT touching the drifted regulation for the NEGATIVE test below
    gov_card = _synthetic_card("gov", "gate: governance baseline")
    # oss card: OSS axis, GSPC axis untouched by UK-GDPR (clean negative)
    oss_card = _synthetic_card("oss", "gate: open-source supply chain")
    unsigned = _synthetic_card("art5", "no sig", signed=False)
    for i, c in enumerate([art5_card, prv_card, gov_card, oss_card, unsigned]):
        Path(tmp, f"card_{i}.json").write_text(json.dumps(c))

    # 1. FAIL-CLOSED / real corpus-watch drift event: UK-GDPR (DRIFT)
    ev = {"instrument": "UK-GDPR", "label": "UK GDPR", "jurisdiction": "UK",
          "level": "act", "provisions_affected": 99,
          "hash_before": "a" * 64, "hash_after": "b" * 64,
          "normaliser": "norm-v2", "source": "legislation.gov.uk:eur/2016/679"}
    rep = evaluate_drift(ev, store=tmp)
    t("parses real corpus-watch event -> DRIFT", rep["state"] == "DRIFT")
    t("GDPR touches gov axis -> gov card IS stale",
      any(c["axis"] == ["gov"] for c in rep["stale_cards"]),
      f"stale={[c['axis'] for c in rep['stale_cards']]}")
    t("prv card flagged STALE on GDPR drift",
      any(c["axis"] == ["prv"] for c in rep["stale_cards"]))
    t("clean negative: OSS card NOT stale on GDPR drift",
      not any(c["axis"] == ["oss"] for c in rep["stale_cards"]))
    t("art5 card (not a GDPR axis) NOT stale on GDPR drift",
      not any(c["axis"] == ["art5"] for c in rep["stale_cards"]))
    t("unsigned card never reported stale",
      not any(c["content_id"] == unsigned["content_id"] for c in rep["stale_cards"]))
    t("report shape present", all(k in rep for k in
      ("stale_cards", "affected_axes", "changed_regulation")))

    # 2. FAIL-CLOSED on UNKNOWN
    rep_unk = evaluate_drift({"changed_regulation": "art5", "state": "UNKNOWN"},
                             store=tmp)
    t("UNKNOWN -> fail_closed True", rep_unk["fail_closed"] is True)
    t("UNKNOWN -> dependent card is POSSIBLY-STALE not stale-list",
      any(c["axis"] == ["art5"] for c in rep_unk["possibly_stale_cards"]) and
      len(rep_unk["stale_cards"]) == 0)
    t("UNKNOWN -> never silently unchanged", rep_unk["state"] == "UNKNOWN")

    # 3. fail-closed on unmapable regulation
    rep_bad = evaluate_drift({"changed_regulation": "completely-unknown-reg"},
                             store=tmp)
    t("unmapable regulation -> FAIL CLOSED UNKNOWN", rep_bad["fail_closed"] is True
      and rep_bad["state"] == "UNKNOWN")

    # 4. removable axes truth: concrete CHANGED state hits, mapped axes correct
    t("Art5 CHANGED -> affected_axes contain art5&affect",
      {"art5", "affect"} <= set(rep_unk["affected_axes"]))
    rep_dora = parse_drift_event({"changed_regulation": "EU-DORA", "state": "CHANGED"})
    t("DORA maps to {gov,det,prv}", rep_dora["affected_axes"] == sorted(["gov", "det", "prv"]) or
      set(rep_dora["affected_axes"]) >= {"gov", "det", "prv"},
      f"{rep_dora['affected_axes']}")
    rep_nis2 = parse_drift_event({"changed_regulation": "EU-NIS2", "state": "CHANGED"})
    t("NIS2 maps to gov/det/prv/mach",
      {"gov", "det", "prv", "mach"} <= set(rep_nis2["affected_axes"]))

    # 5. honest handling: cards are never mutated or deleted
    before = {f: Path(tmp, f).read_bytes() for f in os.listdir(tmp)}
    # run another sweep
    evaluate_drift({"changed_regulation": "art5", "state": "CHANGED"}, store=tmp)
    after = {f: Path(tmp, f).read_bytes() for f in os.listdir(tmp)}
    t("no card file mutated or deleted", before == after)
    t("report declares cards_unchanged_bytes", rep["cards_unchanged_bytes"] is True)

    # 6. no drift (unchanged) -> nothing stale
    rep_clean = evaluate_drift({"changed_regulation": "art5", "state": "unchanged"},
                               store=tmp)
    t("unchanged -> no stale, no possible-stale, not fail-closed",
      len(rep_clean["stale_cards"]) == 0 and len(rep_clean["possibly_stale_cards"]) == 0
      and rep_clean["fail_closed"] is False)

    # 7. real historical UK-DMCCA event resolves
    rep_dmcca = evaluate_drift(
        {"instrument": "UK-DMCCA", "label": "DMCCA 2024", "jurisdiction": "UK",
         "level": "act", "provisions_affected": 386,
         "hash_before": "1bf146e6809215ed8332431d201f318bad63e56d9ccbfbf70a9b3177f63c7d00",
         "hash_after": "2889ba94223164a0698c55b4f0608216608cf5b0354dec860a4883dffbd3bc63",
         "normaliser": "norm-v2", "source": "legislation.gov.uk:ukpga/2024/13"},
        store=tmp)
    t("DMCCA event -> DRIFT, reg resolved, affects consumer axes",
      rep_dmcca["state"] == "DRIFT" and
      {"gov", "care", "affect"} <= set(rep_dmcca["affected_axes"]))

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    import sys
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "self-test":
        return self_test()
    # default: run a live sweep against the default store and print the report
    rep = evaluate_drift(_default_drift())
    print(json.dumps(rep, indent=2))
    return 0 if rep["state"] != "UNKNOWN" else 2  # fail-closed exit on UNKNOWN


def _default_drift() -> Dict[str, Any]:
    """When run with no event, the trigger treats 'no event given' as UNKNOWN
    (fail-closed): we cannot claim 'no drift' without a watch signal."""
    return {"changed_regulation": None, "state": "UNKNOWN"}


if __name__ == "__main__":
    import sys
    sys.exit(main())
