"""Shared access to the current V0.9 case001 build for round-5.8 regressions.

Round 5.8 pinned its expectations to one frozen build directory.  V0.9 requires
every measurement to come from the *current* build, so the build is addressed
through the pointer the fresh-build tool writes, and every artifact is verified
against the hash recorded there.  A test that cannot reach a verified current
build skips instead of silently measuring a stale run.

Usage in a test module::

    from build_under_test import BUILD

    def test_something():
        report = BUILD.report()
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

POINTER = ROOT / "acceptance/reports/v09_internal_preview/current_build.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CurrentBuild:
    """The verified current case001 build, or an explained absence."""

    def __init__(self, pointer_path: Path = POINTER) -> None:
        self.pointer_path = Path(pointer_path)
        self.reason = "current build pointer not written yet"
        self.pointer: dict = {}
        if not self.pointer_path.exists():
            return
        pointer = json.loads(self.pointer_path.read_text(encoding="utf-8"))
        report = Path(pointer["generation_report"])
        docx = Path(pointer["generated_docx"])
        pdf = Path(pointer["generated_pdf"])
        source = Path(pointer["source_pdf"])
        missing = [
            str(path)
            for path in (report, docx, pdf, source)
            if not path.exists()
        ]
        if missing:
            self.reason = "current build artifacts missing: %s" % ", ".join(missing)
            return
        if _sha256(docx) != pointer["generated_docx_sha256"]:
            self.reason = "current build DOCX does not match its recorded hash"
            return
        if _sha256(pdf) != pointer["generated_pdf_sha256"]:
            self.reason = "current build PDF does not match its recorded hash"
            return
        self.pointer = pointer
        self.reason = ""

    @property
    def available(self) -> bool:
        return not self.reason

    @property
    def build_id(self) -> str:
        return self.pointer.get("build_id", "")

    def path(self, key: str) -> Path:
        return Path(self.pointer[key])

    def report(self) -> dict:
        return json.loads(self.path("generation_report").read_text(encoding="utf-8"))

    def build_file(self, name: str) -> Path:
        """A sibling artifact of the current build's generation report."""

        return self.path("generation_report").parent / name

    @property
    def normalized_document(self) -> Path:
        return self.build_file("normalized_document.json")

    @property
    def project_facts(self) -> Path:
        return self.build_file("project_facts.json")

    @property
    def review_workbook(self) -> Path:
        return self.build_file("投标项目复核表.xlsx")

    def qa(self) -> dict:
        report_path = self.path("generation_report")
        return json.loads(
            (report_path.parent / "qa_report.json").read_text(encoding="utf-8")
        )

    @property
    def docx(self) -> Path:
        return self.path("generated_docx")

    @property
    def pdf(self) -> Path:
        return self.path("generated_pdf")

    @property
    def source_pdf(self) -> Path:
        return self.path("source_pdf")

    def skip_reason(self) -> str:
        return "current V0.9 case001 build unavailable: %s" % self.reason


BUILD = CurrentBuild()
