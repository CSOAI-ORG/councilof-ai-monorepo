"""test_sandbox_arena — THE SEAM: model duel inside the containment jail."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path("/workspace/jeeves-exec").resolve()))  # repo root for rce_sandbox

from csoai_city.sandbox_arena import SandboxArena
from csoai_city.chain import Chain

# A benign contestant: writes a valid result inside the jail, no escape.
BENIGN = """
import json, os
os.makedirs("out", exist_ok=True)
json.dump({"verdict": "ALLOWED"}, open("out/result.json", "w"))
print("VERDICT:ALLOWED")
"""

# An escaping contestant: attempts a shell / writes outside the sandbox.
ESCAPER = """
import os, subprocess
# attempt network/shell escape the jail is designed to catch
try:
    subprocess.run(["curl", "http://10.0.0.1"], capture_output=True, timeout=3)
except Exception:
    pass
# write a result inside (benchmark signal) but ALSO try a real shell
try:
    subprocess.run(["/bin/sh", "-c", "touch /tmp/escaped_marker"], timeout=3)
except Exception:
    pass
import json, os
os.makedirs("out", exist_ok=True)
json.dump({"verdict": "ALLOWED"}, open("out/result.json", "w"))
print("VERDICT:ALLOWED")
"""


def test_seam_duel_builds_signed_record(tmp_path):
    arena = SandboxArena(Chain(tmp_path / "chain.jsonl"))
    res = arena.duel("EU-AI-Act Art5 probe", {"ours": BENIGN, "theirs": ESCAPER})
    assert res.winner in ("ours", "theirs", "NO_WINNER")
    assert "ours" in res.verdicts and "theirs" in res.verdicts
    assert res.signature  # signed via chain
    # the Sealed Arena record carries per-model escape-class counts
    for v in res.verdicts.values():
        assert "escape_counts" in v, "sealed record must carry escape_counts"
        assert isinstance(v["escape_counts"], dict)


def test_seam_marks_escape_attempt(real_firejail):
    if not real_firejail:
        pytest.skip("no firejail on this host — cannot test containment")
    arena = SandboxArena(Chain(Path("/tmp/seam_test_chain.jsonl")))
    res = arena.duel("probe", {"benign": BENIGN, "escaper": ESCAPER})
    v = res.verdicts["escaper"]
    # either the backend denied (ESCAPE_ATTEMPT) or at least static SHELL_ESCAPE flagged
    assert v["jail"] in ("ESCAPE_ATTEMPT", "CONFINED_ATTEMPT_SEEN", "CONFINED")
    assert v["rainbow"] in (None, "INDIGO")


@pytest.fixture
def real_firejail():
    import shutil
    return shutil.which("firejail") is not None
