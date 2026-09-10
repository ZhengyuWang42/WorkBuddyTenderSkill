"""Build and validate the distributable tender-basic Skill ZIP."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_package import validate_package


PACKAGE_NAME = "tender-basic-1.0.0.zip"
PACKAGE_ROOT_FILES = (
    "SKILL.md",
    "README.md",
    "MVP_SCOPE.md",
    "requirements.txt",
    "pyproject.toml",
)
PACKAGE_DIRECTORIES = ("tender_basic", "scripts", "rules", "schemas", "references", "templates")
PACKAGE_PREFIX = "tender-basic"


def _package_files() -> list[Path]:
    files: list[Path] = []
    for relative in PACKAGE_ROOT_FILES:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Required package file is missing: {relative}")
        files.append(path)
    for directory in PACKAGE_DIRECTORIES:
        base = ROOT / directory
        if not base.is_dir():
            raise FileNotFoundError(f"Required package directory is missing: {directory}")
        for path in sorted(base.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def build_package(output_path: str | Path | None = None) -> Path:
    target = Path(output_path) if output_path is not None else ROOT / "dist" / PACKAGE_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _package_files():
            relative = path.relative_to(ROOT).as_posix()
            archive.write(path, f"{PACKAGE_PREFIX}/{relative}")

    errors = validate_package(target)
    if errors:
        raise ValueError("Package validation failed: " + "; ".join(errors))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Package the tender-basic WorkBuddy Skill.")
    parser.add_argument("--output", type=Path, help="Optional ZIP output path")
    args = parser.parse_args(argv)
    try:
        output = build_package(args.output)
    except (OSError, ValueError) as exc:
        print(f"Package failed: {exc}", file=sys.stderr)
        return 1
    print("Package: OK")
    print(f"Output: {output}")
    print(f"Size: {output.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
