"""Run pytest with the sandbox mkdir shim and report the exact outcome summary."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A basetemp left behind by a run that could not clean it up keeps the POSIX mode
# pytest created it with, which the file sandbox refuses to enumerate, so every
# later run inherits a setup error from that stale directory.  Each run gets its
# own basetemp instead of reusing one that may already be poisoned.
BASETEMP = ROOT / "acceptance" / "workspace" / ("pytest_tmp_%d" % os.getpid())
BASETEMP.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "acceptance" / "workspace" / "pytest_summary.txt"

command = [
    sys.executable,
    "-X",
    "utf8",
    str(ROOT / "scripts" / "run_pytest_sandbox.py"),
    "-q",
    "tests",
    "-p",
    "no:cacheprovider",
    "--basetemp",
    str(BASETEMP),
]
completed = subprocess.run(
    command, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8"
)
text = (completed.stdout or "") + (completed.stderr or "")
LOG.write_text(text, encoding="utf-8")
print("EXIT", completed.returncode)
for line in text.splitlines():
    if "passed" in line or "failed" in line or "error" in line:
        print(line)
print("LOG", LOG)
