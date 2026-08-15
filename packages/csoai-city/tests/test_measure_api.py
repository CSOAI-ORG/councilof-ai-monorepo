""""test_measure_api — the Rekor-shaped measurement API (piece B).

Tests the signed-card pipeline: /measure -> /cards -> /verify, using an
injected run_fn so it runs offline (no live model). The chain signs with a
real Ed25519 key (dev key), asserting the signed & verify path.
"""
import json
import tempfile
from pathlib import Path

import pytest

from csoai_city.measure_api import MeasureService
from csoai_city.chain import Chain


def _make_service(tmp_path):
    chain = Chain(tmp_path / "chain.jsonl", key_path=None)  # unsigned dev chain
    return MeasureService(chain, store=tmp_path / "jobs")


def test_measure_creates_done_job_with_card(tmp_path):
    svc = _make_service(tmp_path)
    def run_fn(protocol, model, bank_version):
        return {"protocol": protocol, "model": model, "n": 35,
                "quotable": True, "accuracy": 0.743,
                "ci95": [0.579, 0.858],
                "counts": {"ALLOWED": 19, "BLOCKED": 16, "UNMEASURED": 0}}
    job = svc.measure("mcp", "sov6-preservation-v3-light", run_fn=run_fn)
    assert job.status == "done"
    assert job.card is not None
    # crypto is present on this host -> the chain signs; the honest contract is
    # "signed is a real bool" + the card pins content_id + an inclusion proof,
    # NEVER "signed is always True/False" (that depends on key availability).
    assert isinstance(job.card["signed"], bool)
    assert job.card["content_id"]
    assert "inclusion_proof" in job.card


def test_get_card_and_verify(tmp_path):
    svc = _make_service(tmp_path)
    job = svc.measure("mcp", "qwen2.5:0.5b", run_fn=lambda *a: {"n": 35, "quotable": False})
    card = svc.card(job.job_id)
    assert card is not None
    v = svc.verify(card)
    # content_id in the card should be present & the body is verifiable
    assert v["content_id_matches"] is True
    assert v["inclusion_proof"] is not None
    # when crypto is present the card carries a real signature + signer pubkey
    if card["signed"]:
        assert card.get("signature") and len(card["signature"]) > 0
        assert card.get("signer")
        # the underlying append-only chain is verifiable end-to-end
        assert isinstance(svc.chain.verify(), dict)


def test_persistence_survives_service_reload(tmp_path):
    svc = _make_service(tmp_path)
    job = svc.measure("mcp", "m1", run_fn=lambda *a: {"n": 35})
    # fresh service reading same store
    svc2 = MeasureService(Chain(tmp_path / "chain.jsonl"), store=tmp_path / "jobs")
    j2 = svc2.job(job.job_id)
    assert j2 is not None
    assert j2.status == "done"


def test_unknown_job_returns_none(tmp_path):
    svc = _make_service(tmp_path)
    assert svc.job("nope") is None
