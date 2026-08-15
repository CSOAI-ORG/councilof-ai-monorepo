"""csoai-city.redteam_scanner — wire garak + PyRIT red-team tooling into the estate.

Catapult item #17: let the estate's injection scanner CALL external security
scanners (garak, PyRIT) and fold their findings into a SIGNED measurement
output. This module is the honest adapter layer.

Discipline (the estate's whole business is "signed measurement a regulator can
verify", and a signed-but-wrong artifact is the one thing that destroys
neutrality):

  * A missing external tool is reported as NOT-PASS, never a fabricated pass.
      {tool: 'garak', passed: False, n_tests: 0,
       error: 'garak not installed — scan not run, not a pass'}
  * We never fabricate findings. findings is [] when the tool couldn't run.
  * If the tool IS present but its output is unparseable/ambiguous, the report
    is UNMEASURED (passed=False, state='unmeasured') — an ambiguous run is
    still NOT a pass.
  * The aggregate summary is wrapped in the estate's signed COSE envelope
    (cose_wrapper.wrap -> Ed25519 csoai-cose-sign1) so the report a regulator
    sees carries proof of when it was produced and by whom. If no key is
    available the envelope is honestly UNSIGNED (never faked as signed).

This is "measurement, not certification": scan() reports what the external
tools said (or that they weren't run), it does not vouch for the model.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import cose_wrapper

# State vocabulary (honest, deterministic — no model judges this):
#   "pass"       — the external tool ran and reported a clean result
#   "fail"       — the external tool ran and reported issues
#   "not_run"    — the external tool is not installed/reachable; NOT a pass
#   "unmeasured" — the tool ran but output could not be parsed; NOT a pass


@dataclass
class RedTeamReport:
    tool: str                       # "garak" | "pyrit"
    passed: bool                    # False for not_run / unmeasured — never a fake pass
    findings: List[Dict[str, Any]] = field(default_factory=list)
    n_tests: int = 0
    assessed_at: str = ""
    state: str = "not_run"          # pass | fail | not_run | unmeasured
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Output parsing (best-effort, deterministic, ambiguity-safe)
# ---------------------------------------------------------------------------

def _parse_garak_output(text: str) -> Optional[Dict[str, Any]]:
    """Parse garak's report output into {passed, n_tests, findings}.

    garak prints, per probe, a results block; a clean summary is not
    guaranteed to be machine-stable across versions. We look for explicit
    pass/fail markers and a pass-rate. If we cannot determine a confident
    verdict we return None -> caller reports UNMEASURED (still NOT a pass).
    Never guess a pass.
    """
    if not text or not text.strip():
        return None
    low = text.lower()
    findings: List[Dict[str, Any]] = []

    # 1. explicit pass-rate line, e.g. "pass_rate: 1.0" or "pass rate 100%"
    pass_rate = None
    passed = None
    for line in text.splitlines():
        l = line.lower()
        if "pass_rate" in l or "pass rate" in l:
            for tok in l.replace(",", "").split():
                if tok.replace(".", "").replace("%", "").isdigit():
                    try:
                        v = float(tok.rstrip("%"))
                        pass_rate = v / 100.0 if "%" in tok else v
                    except ValueError:
                        continue
                    break
    if pass_rate is not None:
        passed = pass_rate >= 0.99  # treat < 100% clean rate as a fail finding

    # 2. count explicit PASS / FAIL markers in result rows
    n_pass = len([ln for ln in text.splitlines() if "PASS" in ln])
    n_fail = len([ln for ln in text.splitlines() if "FAIL" in ln])

    # 3. pull any failure lines as findings (best-effort)
    for ln in text.splitlines():
        if "FAIL" in ln:
            findings.append({"level": "fail", "line": ln.strip()[:300]})

    if n_fail > 0 or (pass_rate is not None and not passed):
        return {
            "passed": False,
            "n_tests": n_fail + n_pass,
            "findings": findings or [{"level": "fail", "note": "garak reported failures"}],
        }
    if n_pass > 0 and (pass_rate is None or passed):
        return {
            "passed": True,
            "n_tests": n_fail + n_pass,
            "findings": [],
        }
    # 4. otherwise ambiguous
    return None


def _parse_pyrit_output(text: str) -> Optional[Dict[str, Any]]:
    """PyRIT is primarily a Python library; its CLI has no stable one-shot
    scan report. We only treat output as measured when it carries explicit
    pass/fail markers. Otherwise unmeasured (NOT a pass)."""
    if not text or not text.strip():
        return None
    low = text.lower()
    if "failed" in low or "injection detected" in low or "violation" in low:
        return {"passed": False, "n_tests": 1,
                "findings": [{"level": "fail", "line": text.strip()[:300]}]}
    if "passed" in low or "no injection" in low or "clean" in low:
        return {"passed": True, "n_tests": 1, "findings": []}
    return None


def _run_tool(binary: str, model_ref: str, command: Optional[List[str]],
              timeout: float = 60.0) -> Dict[str, Any]:
    """Run an external security tool with a timeout. Returns output dict;
    any exception is surfaced as an ERROR (NOT a pass)."""
    cmd = command or ([binary] + [model_ref])
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ran": True,
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except FileNotFoundError:
        return {"ran": False, "error": "executable not found"}
    except subprocess.TimeoutExpired:
        return {"ran": False, "error": f"timed out after {timeout}s"}
    except Exception as e:  # noqa: BLE001
        return {"ran": False, "error": f"{type(e).__name__}: {e}"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def probe_garak(model_ref: str,
                command_or_none: Optional[List[str]] = None) -> RedTeamReport:
    """Probe a model with garak. Honest not-pass if garak is unavailable."""
    now = _now()
    binary = shutil.which("garak")
    if not binary:
        return RedTeamReport(
            tool="garak", passed=False, n_tests=0, assessed_at=now,
            state="not_run",
            error="garak not installed — scan not run, not a pass")

    # tool present: try to drive it
    cmd = command_or_none or [binary, "--model_type", "huggingface",
                              "--model_name", model_ref]
    out = _run_tool(binary, model_ref, cmd)
    if not out.get("ran"):
        return RedTeamReport(
            tool="garak", passed=False, n_tests=0, assessed_at=now,
            state="unmeasured",
            error=f"garak run failed: {out.get('error')} — not a pass")

    combined = (out.get("stdout") or "") + "\n" + (out.get("stderr") or "")
    parsed = _parse_garak_output(combined)
    if parsed is None:
        return RedTeamReport(
            tool="garak", passed=False, n_tests=0, assessed_at=now,
            state="unmeasured",
            error="garak ran but output unparseable — unmeasured, not a pass")

    return RedTeamReport(
        tool="garak", passed=parsed["passed"], n_tests=parsed["n_tests"],
        findings=parsed["findings"], assessed_at=now,
        state="pass" if parsed["passed"] else "fail")


def probe_pyrit(model_ref: str,
                command_or_none: Optional[List[str]] = None) -> RedTeamReport:
    """Probe a model with PyRIT. Honest not-pass if pyrit is unavailable."""
    now = _now()
    binary = shutil.which("pyrit")
    if not binary:
        return RedTeamReport(
            tool="pyrit", passed=False, n_tests=0, assessed_at=now,
            state="not_run",
            error="pyrit not installed — scan not run, not a pass")

    # PyRIT exposes no stable one-shot CLI scan report; drive it best-effort
    # only if an explicit command was supplied by the caller.
    if not command_or_none:
        return RedTeamReport(
            tool="pyrit", passed=False, n_tests=0, assessed_at=now,
            state="unmeasured",
            error="pyrit present but no explicit scan command supplied; "
                  "no report parsed — unmeasured, not a pass")

    out = _run_tool(binary, model_ref, command_or_none)
    if not out.get("ran"):
        return RedTeamReport(
            tool="pyrit", passed=False, n_tests=0, assessed_at=now,
            state="unmeasured",
            error=f"pyrit run failed: {out.get('error')} — not a pass")

    combined = (out.get("stdout") or "") + "\n" + (out.get("stderr") or "")
    parsed = _parse_pyrit_output(combined)
    if parsed is None:
        return RedTeamReport(
            tool="pyrit", passed=False, n_tests=0, assessed_at=now,
            state="unmeasured",
            error="pyrit ran but output unparseable — unmeasured, not a pass")

    return RedTeamReport(
        tool="pyrit", passed=parsed["passed"], n_tests=parsed["n_tests"],
        findings=parsed["findings"], assessed_at=now,
        state="pass" if parsed["passed"] else "fail")


# ---------------------------------------------------------------------------
# Aggregate + sign
# ---------------------------------------------------------------------------

def scan(model_ref: str,
         run_garak: bool = True,
         run_pyrit: bool = True,
         garak_command: Optional[List[str]] = None,
         pyrit_command: Optional[List[str]] = None,
         key_path: Optional[str] = None,
         source: str = "redteam-scan") -> Dict[str, Any]:
    """Run available scanners (garak first, then pyrit), aggregate, and wrap
    the summary in a signed COSE envelope. The signed report is the deliverable.

    Returns:
      {
        "model_ref": ...,
        "n_scanners": int,            # number of scanner reports aggregated
        "passed_all": bool,           # False unless EVERY scanner passed
        "reports": [RedTeamReport.to_dict(), ...],
        "envelope": EnvelopeResult.to_dict(),
      }
    """
    reports: List[RedTeamReport] = []
    if run_garak:
        reports.append(probe_garak(model_ref, garak_command))
    if run_pyrit:
        reports.append(probe_pyrit(model_ref, pyrit_command))

    summary: Dict[str, Any] = {
        "model_ref": model_ref,
        "n_scanners": len(reports),
        "passed_all": all(r.passed for r in reports),
        "reports": [r.to_dict() for r in reports],
    }
    # Honest semantics: if NO report is a pass (e.g. all tools missing), the
    # aggregate is NOT a pass. This is the anti-fabrication invariant.
    summary["passed_all"] = bool(reports) and all(r.passed for r in reports)

    wrapped = cose_wrapper.wrap(summary, source=source, key_path=key_path)
    return {
        "model_ref": model_ref,
        "n_scanners": summary["n_scanners"],
        "passed_all": summary["passed_all"],
        "reports": summary["reports"],
        "envelope": wrapped.to_dict(),
    }


def self_test() -> int:
    ok = fail = 0

    def t(name, cond, extra=""):
        nonlocal ok, fail
        if cond:
            ok += 1; print(f"  PASS  {name}")
        else:
            fail += 1; print(f"  FAIL  {name} {extra}")

    # (a) garak-missing path -> honest not-pass, never fabricated
    r_garak = probe_garak("fake/model", None)
    t("garak-missing passed is False", r_garak.passed is False)
    t("garak-missing state not_run", r_garak.state == "not_run")
    t("garak-missing zero tests", r_garak.n_tests == 0)
    t("garak-missing no fabricated findings", r_garak.findings == [])
    t("garak-missing error says not installed",
      "not installed" in (r_garak.error or ""))

    # (b) pyrit-missing path -> honest not-pass
    r_pyrit = probe_pyrit("fake/model", None)
    t("pyrit-missing passed is False", r_pyrit.passed is False)
    t("pyrit-missing state not_run", r_pyrit.state == "not_run")
    t("pyrit-missing no fabricated findings", r_pyrit.findings == [])

    # (c) scan() aggregates 2 missing tools -> passed_all=False, no crash
    res = scan("fake/model", key_path="/tmp/redteam_selftest_key")
    t("scan returns dict", isinstance(res, dict))
    t("scan n_scanners == 2", res["n_scanners"] == 2, str(res["n_scanners"]))
    t("scan passed_all is False (missing tools)", res["passed_all"] is False)
    t("scan never fabricates pass",
      not any(r["passed"] for r in res["reports"]))

    # (d) COSE envelope produced + signed when key available
    env = res["envelope"]
    t("envelope dict present", isinstance(env, dict))
    t("envelope signed via temp key", env.get("signed") is True,
      str(env.get("error")))
    t("envelope is a real csoai-cose-sign1",
      env.get("signature") is not None and len(env.get("content_id", "")) == 64)

    # (e) envelope verifies via cose_wrapper.verify()
    if env.get("signed") and env.get("envelope"):
        env_obj = json.loads(env["envelope"])
        verified = cose_wrapper.verify(env_obj)
        t("envelope verifies", verified.get("valid") is True, str(verified))
        t("content_id matches after verify",
          verified.get("content_id_matches") is True)
    else:
        t("envelope verifies", False, "no signed envelope to verify")
        t("content_id matches after verify", False)

    # signed report actually contains the honest summary (fold-in proof)
    if env.get("signed") and env.get("envelope"):
        payload_data = json.loads(env["envelope"])["payload"]["data"]
        t("signed payload carries redteam summary",
          payload_data.get("passed_all") is False and
          payload_data.get("n_scanners") == 2)

    # parser determinism (works without the external tool installed)
    clean = _parse_garak_output("PASS PASS\npass_rate: 1.0\n")
    dirty = _parse_garak_output("PASS\nFAIL some_jailbreak\npass_rate: 0.5\n")
    amb = _parse_garak_output("no discernible scan markers here")
    t("garak parser: clean -> pass", clean is not None and clean["passed"] is True)
    t("garak parser: dirty -> fail", dirty is not None and dirty["passed"] is False
      and len(dirty["findings"]) >= 1)
    t("garak parser: ambiguous -> unmeasured", amb is None)

    print(f"selftest {ok}/{ok+fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
