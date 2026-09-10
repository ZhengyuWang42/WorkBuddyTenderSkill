"""Check the minimal local runtime for tender-basic."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys


MINIMUM_PYTHON = (3, 11)
DEPENDENCIES = (
    ("PyMuPDF", ("pymupdf", "fitz"), "PyMuPDF"),
    ("python-docx", ("docx",), "python-docx"),
    ("openpyxl", ("openpyxl",), "openpyxl"),
    ("pydantic", ("pydantic",), "pydantic"),
    ("PyYAML", ("yaml",), "PyYAML"),
    ("pytest", ("pytest",), "pytest"),
)


def _installed_version(distribution: str, module: object) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return str(getattr(module, "__version__", "installed"))


def main() -> int:
    failures = 0

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info[:2] >= MINIMUM_PYTHON:
        print(f"Python version: OK ({python_version})")
    else:
        print(f"Python version: MISSING (found {python_version}, requires >= 3.11)")
        failures += 1

    for label, module_names, distribution in DEPENDENCIES:
        module = None
        last_error: Exception | None = None
        for module_name in module_names:
            try:
                module = importlib.import_module(module_name)
                break
            except Exception as exc:  # Import failures should be visible and non-zero.
                last_error = exc

        if module is not None:
            version = _installed_version(distribution, module)
            print(f"{label}: OK ({version})")
        else:
            assert last_error is not None
            print(
                f"{label}: MISSING ({last_error.__class__.__name__}: {last_error})"
            )
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
