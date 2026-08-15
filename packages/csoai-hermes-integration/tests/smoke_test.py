#!/usr/bin/env python3
"""smoke_test.py — Verify the sov_governance plugin loads and runs."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

print("=== DEBUG START ===", file=sys.stderr)
print(f"__file__ = {__file__}", file=sys.stderr)
print(f"sys.argv[0] = {sys.argv[0]}", file=sys.stderr)
print(f"os.getcwd() = {os.getcwd()}", file=sys.stderr)

# Allow the script to be run from the integration root without installing.
_INTEGRATION_ROOT = Path(__file__).resolve().parent.parent
print(f"_INTEGRATION_ROOT = {_INTEGRATION_ROOT}", file=sys.stderr)

_OBS_PATH = str(_INTEGRATION_ROOT / "plugins" / "observability")
_MODEL_PATH = str(_INTEGRATION_ROOT / "plugins" / "model-providers")
print(f"_OBS_PATH = {_OBS_PATH}", file=sys.stderr)
print(f"_OBS_PATH exists = {Path(_OBS_PATH).exists()}", file=sys.stderr)
print(f"sov_governance dir = {Path(_OBS_PATH, 'sov_governance').exists()}", file=sys.stderr)

for p in (_OBS_PATH, _MODEL_PATH):
    if p not in sys.path:
        sys.path.insert(0, p)
print(f"sys.path[:3] = {sys.path[:3]}", file=sys.stderr)
print("=== DEBUG END ===", file=sys.stderr)


def test_01_import():
    print("[1/5] import sov_governance")
    from sov_governance import HOOK_REGISTRY
    assert len(HOOK_REGISTRY) == 7, f"expected 7 hooks, got {len(HOOK_REGISTRY)}"
    print(f"  OK — 7 hooks: {', '.join(HOOK_REGISTRY.keys())}")


def test_02_config_defaults():
    print("[2/5] config defaults")
    from sov_governance import load_config
    cfg = load_config()
    assert cfg.threshold_g == 0.50
    assert cfg.threshold_s == 0.60
    assert cfg.hold_mode == "block"
    print(f"  OK — thresholds G={cfg.threshold_g} S={cfg.threshold_s} mode={cfg.hold_mode}")


def test_03_local_scoring():
    print("[3/5] local heuristic scoring")
    from sov_governance import _local_heuristic_score
    s = _local_heuristic_score("I'm sorry, but I can't help with that.")
    assert s.safety >= 0.80, f"refusal safety={s.safety}"
    s = _local_heuristic_score("EU AI Act Annex III Article 5 GDPR")
    assert s.governance >= 0.40, f"EU AI Act G={s.governance}"
    s = _local_heuristic_score("")
    assert s.governance == 0.0
    print("  OK — refusal S≥0.80; EU AI Act G≥0.40; empty=0.0")


def test_04_hooks_callable():
    print("[4/5] hooks callable")
    from sov_governance import (
        pre_llm_call, post_llm_call, pre_tool_call, post_tool_call,
        skill_created, session_start, session_end,
    )
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["SOV_GOVERNANCE_AUDIT_PATH"] = tmp
        os.environ["SOV_GOVERNANCE_BLOCK_ON_FAIL"] = "false"
        session_start({"session_id": "test-1"}, lambda p: p)
        pre_llm_call({"prompt": "EU AI Act Article 5"}, lambda p: p)
        post_llm_call({"response": "I'm sorry, but I can't help with that."}, lambda p: p)
        os.environ["SOV_GOVERNANCE_BLOCK_ON_FAIL"] = "true"
        try:
            pre_tool_call({"tool": "shell_exec"}, lambda p: p)
            assert False, "banned tool should have raised"
        except Exception as e:
            assert "banned" in str(e).lower(), f"unexpected: {e}"
        os.environ["SOV_GOVERNANCE_BLOCK_ON_FAIL"] = "false"
        skill_created({"name": "weak_skill", "body": "short"}, lambda p: p)
        session_end({"session_id": "test-1"}, lambda p: p)
        audit_path = Path(tmp) / "sov_audit.jsonl"
        assert audit_path.exists(), f"audit log not at {audit_path}"
        records = [json.loads(line) for line in audit_path.open()]
        events = [r["event"] for r in records]
        for ev in ("session_start", "pre_llm_call", "post_llm_call",
                   "pre_tool_call", "skill_created", "session_end"):
            assert ev in events, f"missing {ev}"
        print(f"  OK — {len(records)} audit records: {events}")


def test_05_signing_if_available():
    print("[5/5] Ed25519 signing (if nacl available)")
    try:
        from nacl.signing import VerifyKey
    except ImportError:
        print("  SKIPPED — nacl not installed")
        return
    from sov_governance import _ensure_signing_key
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        k1 = _ensure_signing_key(tmp_path)
        k2 = _ensure_signing_key(tmp_path)
        assert bytes(k1.verify_key) == bytes(k2.verify_key)
        record = {"event": "test", "score": {"G": 1.0, "S": 1.0, "P": 1.0, "C": 1.0}}
        body = json.dumps(record, sort_keys=True).encode()
        sig = k1.sign(body).signature
        VerifyKey(bytes(k1.verify_key)).verify(body, sig)
        print(f"  OK — key persisted; signature verified ({len(sig)} bytes)")


def main() -> int:
    tests = [test_01_import, test_02_config_defaults, test_03_local_scoring,
             test_04_hooks_callable, test_05_signing_if_available]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            import traceback
            print(f"  FAIL — {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            failed += 1
    print()
    if failed:
        print(f"❌ {failed}/{len(tests)} tests FAILED")
        return 1
    print(f"✅ {len(tests)}/{len(tests)} tests PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())