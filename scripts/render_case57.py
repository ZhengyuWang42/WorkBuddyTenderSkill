"""Render helpers for the Round 5.7/5.8 geometry + rule-matching QA.

Renders a delivered DOCX with LibreOffice into an isolated user profile and
builds the source-vs-generated comparison images used by the gate reports.

Windows launcher contract (Round 5.8)
-------------------------------------
LibreOffice is always started through ``soffice.com`` with an argv list,
``shell=False``, ``CREATE_NO_WINDOW`` and captured stdout/stderr.  ``soffice.com``
is the console build: it returns a real ``returncode`` and real streams, unlike
``soffice.exe`` which detaches from the console.  Nothing here may go through
``cmd.exe``, ``Start-Process``, Windows Terminal, a ``pause`` wrapper or any
other interactive terminal, and no GUI or console window may appear during an
automated render.  Every render gets its own ``UserInstallation`` profile.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]

#: Console build: reliable stdout/stderr/returncode on Windows.
SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.com")

#: The exact ``-env:UserInstallation`` prefix LibreOffice requires.
PROFILE_URI_PREFIX = "-env:UserInstallation=file:///"

#: No console window, ever, for an automated render.
if hasattr(subprocess, "CREATE_NO_WINDOW"):
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:  # pragma: no cover - non-Windows
    CREATE_NO_WINDOW = 0

CASES = {
    "case_001": ROOT / "acceptance/private/7.28引江济淮郸城配套项目一体化泵站询比文件.pdf",
    "case_002": ROOT / "acceptance/private/营收系统整合和硬件系统升级项目招标文件.pdf",
    "case_003": ROOT / "acceptance/private/肇源县城市供水管网漏损治理项目三标段-招标文件正文.pdf",
}


def source_pdf(case: str) -> Path:
    return CASES[case]


def new_profile(base: Path) -> tuple[Path, str]:
    """A brand-new isolated ``UserInstallation`` profile and its exact URI."""

    profile = (base / f"_lo_profile_{uuid.uuid4().hex[:12]}").resolve()
    profile.mkdir(parents=True, exist_ok=True)
    return profile, PROFILE_URI_PREFIX + profile.as_posix()


def soffice_argv(
    source: Path,
    outdir: Path,
    profile_uri: str,
    *,
    convert_to: str = "pdf",
    extra: list[str] | None = None,
) -> list[str]:
    """The exact argv list for one headless conversion or query."""

    argv = [str(SOFFICE), profile_uri]
    if extra:
        argv.extend(extra)
    argv.extend(["--headless", "--norestore", "--invisible"])
    if convert_to:
        argv.extend(["--convert-to", convert_to, "--outdir", str(outdir), str(source)])
    return argv


def run_soffice(argv: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess:
    """Run LibreOffice headless with no window and captured streams."""

    return subprocess.run(
        argv,
        shell=False,
        capture_output=True,
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def render_docx(docx: Path, outdir: Path, profile: Path | None = None) -> Path:
    """Render ``docx`` to PDF in ``outdir`` and return the PDF path."""

    if not SOFFICE.exists():
        raise FileNotFoundError(f"LibreOffice console build not found at {SOFFICE}")
    docx = docx.resolve()
    outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    profile_dir, profile_uri = new_profile(profile or outdir)
    target = outdir / (docx.stem + ".pdf")
    if target.exists():
        target.unlink()
    result = run_soffice(soffice_argv(docx, outdir, profile_uri))
    if result.returncode != 0:
        raise RuntimeError(
            "LibreOffice render failed with returncode "
            f"{result.returncode}: {result.stderr.decode('utf-8', 'replace')[:500]}"
        )
    if not target.exists():
        raise RuntimeError(f"LibreOffice produced no PDF for {docx}")
    return target


def stack_pages(left: pymupdf.Page, right: pymupdf.Page, target: Path, zoom: float = 2.0) -> Path:
    left_pix = left.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    right_pix = right.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    width = left_pix.width + right_pix.width + 12
    height = max(left_pix.height, right_pix.height)
    canvas = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height))
    canvas.set_rect(canvas.irect, (255, 255, 255))
    canvas.copy(left_pix, pymupdf.IRect(0, 0, left_pix.width, left_pix.height))
    canvas.copy(
        right_pix,
        pymupdf.IRect(
            left_pix.width + 12, 0, left_pix.width + 12 + right_pix.width, right_pix.height
        ),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    return target


def overlay_pages(left: pymupdf.Page, right: pymupdf.Page, target: Path, zoom: float = 2.0) -> Path:
    """Paint the source ink in red on top of the generated render.

    Both pages are rasterised at the same zoom, so a red mark with no dark mark
    underneath is source-only: the source draws a rule where the delivery does
    not.  A dark mark with no red is delivery-only.
    """

    source = left.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    generated = right.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    width = max(source.width, generated.width)
    height = max(source.height, generated.height)
    src = memoryview(source.samples).cast("B")
    gen = memoryview(generated.samples).cast("B")
    data = bytearray(width * height * 3)
    for row in range(height):
        out_row = row * width * 3
        pixel = bytearray(b"\xff\xff\xff") * width
        if row < generated.height:
            start = row * generated.stride
            pixel[: generated.width * 3] = bytes(
                gen[start : start + generated.width * 3]
            )
        if row < source.height:
            start = row * source.stride
            for column in range(min(source.width, width)):
                offset = start + column * source.n
                if src[offset] < 160:
                    index = column * 3
                    pixel[index] = 0xFF
                    pixel[index + 1] = 0x00
                    pixel[index + 2] = 0x00
        data[out_row : out_row + width * 3] = bytes(pixel)
    canvas = pymupdf.Pixmap(pymupdf.csRGB, width, height, bytes(data), False)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target)
    return target


__all__ = ["CASES", "overlay_pages", "render_docx", "source_pdf", "stack_pages"]
