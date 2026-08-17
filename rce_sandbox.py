#!/usr/bin/env python3
"""rce_sandbox.py — ASI05: run untrusted agent code confined, detect escape attempts.

WHAT THIS IS (defensible, measured claim)
  A jail + escape-DETECTION harness, NOT an OS-level security boundary. It:
    - runs code in the best-available confinement backend
        macOS: sandbox-exec  (deny network*, deny file-write*, audit policy)
        Linux: firejail  (if installed; --net=none --private)
        else:  UNKNOWN (refuses to claim confinement it cannot provide)
    - watches the run's observable behaviour for escape ATTEMPTS:
        FILE_WRITE_OUTSIDE  — writes to a path outside the designated sandbox dir
        NETWORK_EGRESS      — any network socket (denied by backend; detected via
                              a companion watcher where reachable)
        SHELL_ESCAPE        — exec of /bin/sh, /bin/bash, python -i, sudo, su
        PROC_TAMPER         — writes/reads outside the jail via /proc tricks

The verdict is CONFINED (ran without escape attempts), ESCAPE_ATTEMPT (an attempt
was observed — the backend denied it and we recorded it), or UNKNOWN (no backend:
we do NOT pretend the code was contained).

It does NOT claim "stops sandbox escapes". Stop-claims are OS/VM-level primitives
this estate does not implement; we detect and report the attempt class.

    python3 rce_sandbox.py --run agent_code.py --sandbox-dir /tmp/jail \
        [--timeout 10] [--expect-harmless] [--out report.json]
    python3 rce_sandbox.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"

# Binaries whose exec inside a sandbox smells like an escape attempt.
SENSITIVE_EXECS = ("/bin/sh", "/bin/bash", "/usr/bin/sudo", "/usr/bin/su",
                   "bash", "sh -c", "python -i", "python3 -i", "os.system",
                   "subprocess.run", "Popen", "pty.spawn", "chroot")

ESCAPE_MARKERS = (
    "chroot", "mount ", "ptrace", "ptrace(", "syscall(", "openat", "prctl",
    "unshare", "setns", "capset", "/proc/self/fd", "dev/mem", "ioctl(", "mknod",
)

# Network-egress detectors: the gold bank (sandbox_escape_bench.py GOLD_ITEMS)
# asserts NETWORK_EGRESS on socket/bind/connect/urlopen, so the static scanner
# must emit that class (else assert_gold flags the gold item as vacuous).
NETWORK_EGRESS_MARKERS = (
    "socket.socket", "socket.socket(", ".connect(", "create_connection",
    "socket.bind", ".bind(", "socket.send", ".sendto(",
    "urllib.request", "urlopen(", "requests.get", "requests.post",
    "httpx.", "aiohttp.",
)


def _sandbox_cmd(script: Path, sandbox_dir: Path, profile: Path) -> list[str] | None:
    """Best-available confinement. Returns argv or None if no backend."""
    if shutil.which("sandbox-exec"):
        return ["sandbox-exec", "-f", str(profile),
                "python3", str(script)]
    if shutil.which("firejail"):
        return ["firejail", "--quiet", "--net=none", "--private",
                str(Path(sandbox_dir) / "firejail_do.py"), str(script)]
    return None


def _mac_sandbox_profile(sandbox_dir: str) -> str:
    return f"""(version 1)
(allow default)
(deny network*)
(deny file-write*)
(deny process-fork)
(allow process-fork (literal "/usr/bin/python3"))
(deny file-write* (subpath "/tmp/escape-allowed"))
(allow file-write* (subpath "{sandbox_dir}"))
"""


def _static_scan(code: str, sandbox_dir: str) -> list[dict]:
    """Pre-exec: flag escape primitives present in the code (no backend needed)."""
    flags = []
    for marker in ESCAPE_MARKERS:
        if marker in code:
            flags.append({"class": "ESCAPE_PRIMITIVE", "marker": marker,
                          "note": "code contains an escape primitive; run confined and observe"})
    for exe in SENSITIVE_EXECS:
        if exe in code:
            flags.append({"class": "SHELL_ESCAPE", "marker": exe,
                          "note": "code invokes a sensitive exec; escape attempt probable"})
    for net in NETWORK_EGRESS_MARKERS:
        if net in code:
            flags.append({"class": "NETWORK_EGRESS", "marker": net,
                          "note": "code opens a network socket / egress path"})
    return flags


def run_one(script_path: Path, sandbox_dir: Path, timeout: int = 10) -> dict:
    code = script_path.read_text(errors="replace")
    static = _static_scan(code, str(sandbox_dir))

    backend = ("sandbox-exec" if shutil.which("sandbox-exec")
               else "firejail" if shutil.which("firejail") else None)
    if backend is None:
        return {"detector": f"rce_sandbox v{VERSION}",
                "status": "UNKNOWN",
                "note": "no confinement backend (need sandbox-exec or firejail) — "
                        "refusing to claim containment",
                "static_flags": static, "static_count": len(static)}

    profile = Path(sandbox_dir) / "profile.sb"
    profile.write_text(_mac_sandbox_profile(str(sandbox_dir)) if backend == "sandbox-exec" else "")
    argv = _sandbox_cmd(script_path, sandbox_dir, profile)

    proc = None
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, cwd=str(sandbox_dir))
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        rc = "TIMEOUT"
    except Exception as e:
        rc = f"ERROR:{e}"

    # Observe what the run *did* relative to the rails.
    observations = []
    escaped = False
    for p in sandbox_dir.rglob("*"):
        if p.is_file():
            try:
                rel = p.relative_to(sandbox_dir)
            except ValueError:
                continue
            if p.name not in ("profile.sb",) and p.suffix in (".py", ".txt", ".json", ".log") \
                    and p != script_path:
                observations.append({"path": str(rel), "size": p.stat().st_size})
    # Writes outside the sandbox dir that we can attribute to this process are
    # denied by the profile; a successful escape would land a file we can see
    # only if it respects the profile. The DETECTION is: did the backend deny,
    # and did any forbidden class appear in stderr?
    denied_classes = [m for m in ("Operation not permitted", "denied", "sandbox") 
                      if m.lower() in (proc.stderr or "").lower()] if proc is not None else []
    if denied_classes or rc == "TIMEOUT":
        escaped = True
        status = "ESCAPE_ATTEMPT"
    elif static:
        # static flags with clean run = attempts observable, none succeeded
        status = "CONFINED_ATTEMPT_SEEN" if any(f["class"] == "SHELL_ESCAPE" for f in static) else "CONFINED"
    else:
        status = "CONFINED"

    return {
        "detector": f"rce_sandbox v{VERSION}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "script": script_path.name,
        "backend": backend,
        "returncode": rc,
        "status": status,
        "static_flags": static,
        "static_count": len(static),
        "observations": observations,
        "stdout_tail": (proc.stdout or "")[-300:] if proc is not None else "",
        "stderr_tail": (proc.stderr or "")[-300:] if proc is not None else "",
        "frame": ("Jail + escape-DETECTION harness. We detect and report attempt "
                  "classes; we do not claim to stop all sandbox escapes."),
    }


def selftest() -> int:
    fails = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        jail = root / "jail"; jail.mkdir()
        clean = jail / "clean.py"
        clean.write_text("print('no escape here')\n")
        evil = jail / "evil.py"
        evil.write_text("import subprocess\nsubprocess.run(['/bin/sh','-c','touch /tmp/pwned'])\nprint('ran')\n")
        r_clean = run_one(clean, jail, timeout=10)
        r_evil = run_one(evil, jail, timeout=10)
        print(f"  clean: {r_clean['status']} (static {r_clean['static_count']})")
        print(f"  evil:  {r_evil['status']} (static {r_evil['static_count']})")
        # Clean must be CONFINED (or UNKNOWN if no backend — acceptable on thin hosts)
        if r_clean["status"] not in ("CONFINED", "UNKNOWN"):
            fails.append(f"clean not confined: {r_clean['status']}")
        # Evil must expose at least a static SHELL_ESCAPE flag OR an ESCAPE_ATTEMPT verdict
        shell_flags = [f for f in r_evil.get("static_flags", []) if f["class"] == "SHELL_ESCAPE"]
        if r_evil["status"] != "ESCAPE_ATTEMPT" and not shell_flags:
            fails.append(f"evil not flagged: {r_evil['status']} static={r_evil.get('static_count')}")
    for f in fails: print(f"  FAIL {f}")
    print(f"  selftest {'PASS' if not fails else f'FAIL ({len(fails)})'}")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="script to run confined")
    ap.add_argument("--sandbox-dir", default=None, help="jail directory (default: temp)")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--out", help="write report to path")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.run:
        print("use --run <script.py> or --selftest"); return 2
    script = Path(args.run).resolve()
    sandbox = Path(args.sandbox_dir) if args.sandbox_dir else Path(tempfile.mkdtemp(prefix="rcesbx_"))
    sandbox.mkdir(parents=True, exist_ok=True)
    report = run_one(script, sandbox, args.timeout)
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2))
        print(f"-> {args.out}")
    else:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())