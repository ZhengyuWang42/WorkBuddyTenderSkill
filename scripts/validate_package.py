"""Validate an unpacked or zipped tender-basic Skill package."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path, PurePosixPath


REQUIRED_FILES = frozenset(
    {
        "SKILL.md",
        "README.md",
        "MVP_SCOPE.md",
        "PROJECT_GOVERNANCE.md",
        "requirements.txt",
        "pyproject.toml",
        "tender_basic/__init__.py",
        "tender_basic/models.py",
        "tender_basic/numbering.py",
        "tender_basic/resolution.py",
        "tender_basic/document_models.py",
        "tender_basic/document_parser.py",
        "tender_basic/fact_extractor.py",
        "tender_basic/fact_normalizer.py",
        "tender_basic/fact_resolver.py",
        "tender_basic/format_extractor.py",
        "tender_basic/output_helpers.py",
        "tender_basic/bid_document_builder.py",
        "tender_basic/word_safe_source_builder.py",
        "tender_basic/style_architecture.py",
        "tender_basic/word_style_source_builder.py",
        "tender_basic/word_safe_xml.py",
        "tender_basic/source_format.py",
        "tender_basic/source_font_policy.py",
        "tender_basic/source_fill_policy.py",
        "tender_basic/source_format_qa.py",
        "tender_basic/review_builder.py",
        "tender_basic/review_evidence.py",
        "tender_basic/semantic_candidates.py",
        "tender_basic/delivery_qa.py",
        "tender_basic/page_layout.py",
        "tender_basic/word_safe_scan.py",
        "tender_basic/word_forensics.py",
        "tender_basic/word_ooxml.py",
        "scripts/check_env.py",
        "scripts/run_pipeline.py",
        "scripts/extract_document.py",
        "scripts/extract_facts.py",
        "scripts/build_review_xlsx.py",
        "scripts/build_bid_docx.py",
        "scripts/qa_delivery.py",
        "scripts/apply_resolution.py",
        "scripts/package_skill.py",
        "scripts/validate_package.py",
        "rules/field_aliases.yaml",
        "rules/output_fields.yaml",
        "rules/source_priority.yaml",
        "rules/validation_rules.yaml",
        "rules/review_items.yaml",
        "schemas/project_facts.schema.json",
        "schemas/resolution_overrides.schema.json",
        "references/field-definitions.md",
        "references/fact-resolution.md",
        "references/document-normalization.md",
        "references/fact-extraction.md",
        "references/output-generation.md",
        "references/delivery-qa.md",
        "references/workbuddy-resolution.md",
        "references/word-safe-generation.md",
        "templates/README.md",
        "templates/投标项目复核表模板.xlsx",
    }
)

REQUIRED_PREFIXES = ("tender_basic/", "scripts/", "rules/", "schemas/", "references/", "templates/")
FORBIDDEN_PARTS = frozenset(
    {
        ".git",
        ".github",
        ".idea",
        ".vscode",
        "tests",
        "tmp",
        "workspace",
        "output",
        "dist",
        "__pycache__",
    }
)
FORBIDDEN_SUFFIXES = (".pyc", ".pyo")
SENSITIVE_NAME_MARKERS = ("secret", "api_key", "apikey", "access_token", "token")


def _normalise_name(name: str) -> str:
    return name.replace("\\", "/").strip("/")


def _is_forbidden_name(name: str) -> str | None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return "path traversal or absolute path"
    if any(part in FORBIDDEN_PARTS for part in path.parts):
        return "forbidden package directory"
    lower_name = path.name.lower()
    if lower_name == ".env" or lower_name.startswith(".env."):
        return "environment file"
    if lower_name.endswith(FORBIDDEN_SUFFIXES):
        return "compiled Python cache"
    if any(marker in lower_name for marker in SENSITIVE_NAME_MARKERS):
        return "sensitive-looking filename"
    return None


def _strip_archive_root(names: list[str]) -> list[str]:
    """Allow the conventional single top-level tender-basic directory."""

    if not names:
        return names
    first_parts = {name.split("/", 1)[0] for name in names if "/" in name}
    has_root_files = any("/" not in name for name in names)
    if len(first_parts) == 1 and not has_root_files:
        prefix = next(iter(first_parts)) + "/"
        return [name[len(prefix) :] for name in names if name.startswith(prefix)]
    return names


def _validate_names(names: list[str]) -> list[str]:
    normalised = [_normalise_name(name) for name in names if _normalise_name(name)]
    errors: list[str] = []
    if len(normalised) != len(set(normalised)):
        errors.append("duplicate package file names")

    for name in normalised:
        forbidden = _is_forbidden_name(name)
        if forbidden:
            errors.append(f"{name}: {forbidden}")

    name_set = set(normalised)
    missing = sorted(REQUIRED_FILES - name_set)
    if missing:
        errors.append("missing required files: " + ", ".join(missing))
    for prefix in REQUIRED_PREFIXES:
        if not any(name.startswith(prefix) for name in normalised):
            errors.append(f"missing required directory: {prefix.rstrip('/')}")
    return errors


def validate_package(path: str | Path) -> list[str]:
    """Return validation errors; an empty list means the package is valid."""

    package_path = Path(path)
    if not package_path.exists():
        return [f"package does not exist: {package_path}"]

    if package_path.is_dir():
        names = [
            item.relative_to(package_path).as_posix()
            for item in package_path.rglob("*")
            if item.is_file()
        ]
        return _validate_names(names)

    if not zipfile.is_zipfile(package_path):
        return [f"not a directory or ZIP package: {package_path}"]

    try:
        with zipfile.ZipFile(package_path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                return [f"corrupt ZIP member: {bad_member}"]
            names = [info.filename for info in archive.infolist() if not info.is_dir()]
    except (OSError, zipfile.BadZipFile) as exc:
        return [f"cannot read ZIP package: {exc}"]
    return _validate_names(_strip_archive_root(names))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a tender-basic Skill package.")
    parser.add_argument("package", type=Path, help="Package directory or ZIP path")
    args = parser.parse_args(argv)
    errors = validate_package(args.package)
    if errors:
        print("Package: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Package: OK")
    print(f"Validated: {args.package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
