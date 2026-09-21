from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.package_skill import build_package
from scripts.validate_package import validate_package


def test_package_is_complete_and_has_no_forbidden_files(tmp_path: Path) -> None:
    package_path = build_package(tmp_path / "tender-basic-1.0.0.zip")

    assert package_path.is_file()
    assert package_path.stat().st_size > 0
    assert validate_package(package_path) == []
    with zipfile.ZipFile(package_path) as archive:
        names = set(archive.namelist())
        assert "tender-basic/SKILL.md" in names
        assert "tender-basic/PROJECT_GOVERNANCE.md" in names
        assert "tender-basic/scripts/run_pipeline.py" in names
        assert "tender-basic/scripts/apply_resolution.py" in names
        assert "tender-basic/tender_basic/numbering.py" in names
        assert "tender-basic/tender_basic/style_architecture.py" in names
        assert "tender-basic/tender_basic/word_style_source_builder.py" in names
        assert "tender-basic/schemas/resolution_overrides.schema.json" in names
        assert not any("/tests/" in name or "__pycache__" in name for name in names)


def test_validator_rejects_forbidden_package_members(tmp_path: Path) -> None:
    package_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("tender-basic/SKILL.md", "---\nname: tender-basic\n---\n")
        archive.writestr("tender-basic/tests/test_secret.py", "secret")

    errors = validate_package(package_path)
    assert any("forbidden package directory" in error for error in errors)


def test_validator_rejects_missing_runtime_contract_files(tmp_path: Path) -> None:
    source_package = build_package(tmp_path / "complete.zip")
    incomplete_package = tmp_path / "missing-review-rules.zip"

    with zipfile.ZipFile(source_package) as source, zipfile.ZipFile(
        incomplete_package, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for info in source.infolist():
            if info.filename != "tender-basic/rules/review_items.yaml":
                target.writestr(info, source.read(info.filename))

    errors = validate_package(incomplete_package)
    assert any(
        "missing required files" in error and "rules/review_items.yaml" in error
        for error in errors
    )
