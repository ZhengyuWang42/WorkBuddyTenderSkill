"""Optional pytest compatibility plugin for Windows hosts with restrictive ACLs.

Environment compatibility infrastructure - **not** product code, **not** an
assertion, and never imported by ``tender_basic`` or by any test module.

The problem
-----------

pytest's temporary-directory factory creates every ``tmp_path`` directory with
``pathlib.Path.mkdir(mode=0o700)``.  On the Windows host this project is
developed on, a directory created that way cannot afterwards be enumerated by
the process that created it::

    PermissionError: [WinError 5] 拒绝访问。: '...\\pytest-of-WPG'

pytest calls ``os.scandir`` on that directory both when it hands out the first
``tmp_path`` and again at session finish (``cleanup_dead_symlinks``), so every
test that uses ``tmp_path`` errors and the session exits non-zero even when the
code under test is fine.

What this plugin does
---------------------

It restores the default mode for ``Path.mkdir`` calls that ask for ``0o700``.
The mode is a permission *request*, not part of any test's contract, and no test
in this repository asserts on the mode of its temporary directory.  Nothing else
is changed: no assertion, no fixture, no test body, no product module.

How it is activated
-------------------

It is **not** auto-loaded.  Ordinary runs stay untouched::

    pytest -q

On an affected Windows host, load it explicitly for that run only::

    set PYTHONPATH=%CD%\\scripts\\dev
    set PYTEST_PLUGINS=pytest_fscompat
    pytest -q --basetemp <fresh writable directory>

or use ``scripts/run_full_tests_windows.ps1``, which performs exactly those two
steps, picks a fresh writable basetemp, and writes the run's evidence.

The plugin refuses to do anything on a host where the environment variable
``PYTEST_FSCOMPAT_FORCE`` is unset and the platform is not Windows, so a
non-Windows CI run that accidentally loads it is a no-op.
"""

from __future__ import annotations

import os
import pathlib
import sys

RESTRICTIVE_MODE = 0o700

_ORIGINAL_MKDIR = pathlib.Path.mkdir


def _mkdir(self, mode=0o777, parents=False, exist_ok=False):
    """``Path.mkdir`` with the restrictive temporary-directory mode relaxed."""

    if mode == RESTRICTIVE_MODE:
        mode = 0o777
    return _ORIGINAL_MKDIR(self, mode, parents=parents, exist_ok=exist_ok)


def is_affected_host() -> bool:
    """True on the platforms whose ``mkdir(mode=0o700)`` breaks enumeration."""

    return sys.platform == "win32" or bool(os.environ.get("PYTEST_FSCOMPAT_FORCE"))


def pytest_configure(config):  # noqa: ARG001 - pytest hook signature
    """Install the shim only on an affected host, and say so in the header."""

    if not is_affected_host():
        return
    pathlib.Path.mkdir = _mkdir
    config.stash  # noqa: B018 - touch the config so the hook is obviously live
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line(
            "pytest_fscompat: Path.mkdir(mode=0o700) relaxed to the default mode "
            "(Windows temporary-directory ACL compatibility; no assertion changed)"
        )


def pytest_unconfigure(config):  # noqa: ARG001 - pytest hook signature
    """Restore the original ``mkdir`` so the shim cannot leak into other tools."""

    pathlib.Path.mkdir = _ORIGINAL_MKDIR
