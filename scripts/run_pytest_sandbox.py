"""Run pytest with the DSH sandbox-safe mkdir shim.

The DSH file sandbox denies ``os.scandir`` on directories created with the POSIX
mode ``0o700`` that pytest's tmp_path factory uses.  This wrapper strips the mode
argument before delegating, so pytest's own temporary-directory handling works.
It changes nothing about the tests themselves and is only needed when pytest is
driven from inside the sandbox; a normal shell can run ``pytest`` directly.

Usage::

    .venv/Scripts/python.exe scripts/run_pytest_sandbox.py -q tests
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Running this file puts ``scripts/`` on sys.path[0]; the suite imports the
# repository packages by name, so the repository root must come first.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_real_mkdir = os.mkdir


def _mkdir(path, mode=0o777, *args, **kwargs):  # noqa: ANN001
    return _real_mkdir(path, 0o777, *args, **kwargs)


os.mkdir = _mkdir

import pytest  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(pytest.main(sys.argv[1:]))
