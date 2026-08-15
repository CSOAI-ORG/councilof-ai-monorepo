#!/usr/bin/env python3
"""Pod-side master verification — run ALL sovereign wires' selftests on the A100.

The single source of truth for "are we 100%": every module that the measurement
spine depends on, tested where the work actually runs (the pod), not the Mac.
"""
import importlib
import sys
import json
from datetime import datetime, timezone

WIRES = [
    # (module, label)
    ("csoai_city.correctness_gate",    "Wire 1 correctness gate"),
    ("csoai_city.attestation_registry", "Wire 2 attestation->SOV signal"),
    ("csoai_city.timestamping",        "Wire 3 time-anchoring (OTS)"),
    ("csoai_city.drift_re_attestation", "Wire 4 drift-triggered re-attestation"),
    ("csoai_city.cose_wrapper",        "Wire 5 COSE signing wrapper"),
    ("csoai_city.adoption_space",      "J-Space 1 adoption leg"),
    ("csoai_city.measure_api",         "Enforced issuance choke point"),
    ("csoai_city.telemetry",           "Self-instrumentation (signed telemetry)"),
    ("csoai_city.underwriting_pack",   "Diamond-3 underwriting input"),
    ("csoai_city.redteam_scanner",     "Red-team scanner (garak/PyRIT adapter)"),
    ("csoai_city.bom_signer",          "AI-BOM signed spine"),
]

results = []
exit_code = 0

for mod_name, label in WIRES:
    try:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "self_test"):
            # redirect stdout to capture PASS/FAIL lines
            import io
            buf = io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                rc = mod.self_test()
            finally:
                sys.stdout = old
            lines = buf.getvalue().strip().splitlines()
            pass_line = lines[-1] if lines else "no output"
            ok = rc == 0
            if not ok:
                exit_code = 1
            results.append({
                "label": label, "module": mod_name, "pass": ok,
                "summary": pass_line,
                "detail": "\n".join(lines[-3:]),
            })
        else:
            results.append({"label": label, "module": mod_name, "pass": False,
                            "summary": "no self_test"})
            exit_code = 1
    except Exception as e:  # noqa: BLE001
        results.append({"label": label, "module": mod_name, "pass": False,
                        "summary": f"IMPORT FAIL: {type(e).__name__}: {e}"})
        exit_code = 1

report = {
    "host": "A100-pod",
    "run_at": datetime.now(timezone.utc).isoformat(),
    "n_wires": len(results),
    "n_pass": sum(1 for r in results if r["pass"]),
    "exit_code": exit_code,
    "wires": results,
}
print(json.dumps(report, indent=2))
sys.exit(exit_code)
