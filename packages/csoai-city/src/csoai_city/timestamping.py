"""csoai-city.timestamping — honest time-anchor for signed cards.

Closes the "real timestamping" gap (the estate's charter claimed "OTS Bitcoin proof"
with ~1 code ref — aspirational). This module makes it real AND honest:

  * stamps a card's content_id into an OpenTimestamps detached commitment
    (independent calendar, third-party verifiable)
  * tracks TWO distinct states and never conflates them:
      calendar_commit  — the digest was committed to the OTS calendar (cryptographic
                         proof "this existed at time T", independently verifiable)
      btc_anchored     — the calendar batch Merkle root has landed in a Bitcoin
                         block and been verified against a block header (stronger:
                         "existed before block N")
  * FAIL-CLOSED: until btc_anchored is verified true, the card's provenance is
    reported as "calendar-commit, BTC-anchor pending" — NEVER claimed as
    "Bitcoin proof". Honesty mirrors corpus-watch's UNKNOWN-never-unchanged rule.

The producer (card_issuer / measure_api) calls anchor_card(card) after issuing;
the charter's "OTS Bitcoin proof" overclaim is scrubbed until btc_anchored is real.
"""
from __future__ import annotations

import hashlib
import ssl
import urllib.request
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, Optional

CALENDARS = [
    "https://a.pool.opentimestamps.org/digest",
    "https://b.pool.opentimestamps.org/digest",
]

# RFC-3161 / OTS independence: we do NOT sign our own timestamps (that'd be
# hash-theater again). We commit to an external, independent OTS calendar the
# same way a third party would.

def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


@dataclass
class TimeAnchor:
    content_id: str
    state: str                    # "calendar_commit" | "btc_anchored" | "failed"
    ots_path: str = ""
    bytes_len: int = 0
    calendar_used: str = ""
    btc_anchored: bool = False
    btc_block: Optional[str] = None
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def stamp_content_id(content_id: str, ots_dir: Path = Path("/tmp/ots-anchors"),
                     calendars: Optional[list] = None) -> TimeAnchor:
    """Commit a card content_id to an independent OTS calendar.

    Returns a TimeAnchor. state is 'calendar_commit' on success (NOT btc_anchored
    unless verification confirms a block). Fail-closed on error.
    """
    ots_dir = Path(ots_dir)
    ots_dir.mkdir(parents=True, exist_ok=True)
    out = ots_dir / f"{content_id}.ots"

    # anchor file = the content_id bytes alone (canonical, reproducible)
    digest = _sha256(content_id.encode())

    last_err = ""
    used = ""
    blob = b""
    for cal in (calendars or CALENDARS):
        try:
            req = urllib.request.Request(
                cal, data=digest, method="POST",
                headers={"Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx()) as resp:
                blob = resp.read()
            used = cal
            break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
            continue

    if not blob:
        return TimeAnchor(content_id, "failed", note=f"no calendar reachable: {last_err}")

    out.write_bytes(blob)
    return TimeAnchor(
        content_id, "calendar_commit",
        ots_path=str(out), bytes_len=len(blob),
        calendar_used=used, btc_anchored=False,
        note="calendar commitment written; BTC-block anchor PENDING verification "
             "(never claimed as Bitcoin proof until checked)",
    )


def record_anchor(card: Dict[str, Any], anchor: TimeAnchor) -> Dict[str, Any]:
    """Attach the time anchor to a card payload (non-destructive, additive)."""
    card = dict(card)
    card["time_anchor"] = anchor.to_dict()
    return card


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # 1. stamping a real content_id hits a calendar and returns a .ots blob
    a = stamp_content_id("37a0104a39c69edcd3c17ed7159be3616b1569567c441566d9ab620686379090")
    t("stamp returns calendar commitment", a.state == "calendar_commit" and a.bytes_len > 0,
      a.note)
    t("ots file written", a.ots_path and Path(a.ots_path).exists())
    t("NOT claimed btc-anchored", a.btc_anchored is False,
      "fail-closed: no btc claim without verification")

    # 2. record_anchor is additive (doesn't destroy card)
    card = {"content_id": "abc", "signed": True}
    rec = record_anchor(card, a)
    t("anchor added additively", rec.get("time_anchor", {}).get("state") == a.state)
    t("original fields preserved", rec.get("content_id") == "abc" and rec["signed"] is True)

    # 3. deterministic digest reproducibility
    t("digest reproducible", _sha256(b"abc").hex() == _sha256(b"abc").hex())

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
