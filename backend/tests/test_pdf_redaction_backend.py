from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from wmrm.adapters.pdf.pymupdf_redaction import (
    PdfRedactionError,
    probe_pymupdf,
    redact_pdf_regions,
)
from wmrm.benchmarks.pdf_redaction_probe import _fixture_pdf, run_probe


def test_redaction_rejects_unknown_license_mode(tmp_path: Path) -> None:
    with pytest.raises(PdfRedactionError, match="许可证模式"):
        redact_pdf_regions(
            tmp_path / "source.pdf",
            tmp_path / "result.pdf",
            [{"page_number": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
            license_mode="unset",  # type: ignore[arg-type]
        )


def test_pymupdf_redaction_probe() -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    report = run_probe()
    assert report["passed"] is True
    assert all(report["checks"].values())


def test_redaction_rejects_out_of_bounds_region(tmp_path: Path) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())
    with pytest.raises(PdfRedactionError, match="超出"):
        redact_pdf_regions(
            source,
            tmp_path / "result.pdf",
            [{"page_number": 1, "x0": 0, "y0": 0, "x1": 700, "y1": 20}],
            license_mode="agpl",
        )


def test_redaction_converts_crop_relative_coordinates_on_rotated_page(
    tmp_path: Path,
) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())
    cropped = tmp_path / "cropped.pdf"
    writer = PdfWriter(clone_from=PdfReader(str(source)))
    page = writer.pages[0]
    page.cropbox.lower_left = (10, 20)
    page.cropbox.upper_right = (602, 772)
    page.rotate(90)
    with cropped.open("wb") as output:
        writer.write(output)

    result = tmp_path / "result.pdf"
    redact_pdf_regions(
        cropped,
        result,
        [{"page_number": 1, "x0": 80, "y0": 660, "x1": 235, "y1": 715}],
        license_mode="agpl",
    )

    output = PdfReader(str(result), strict=True)
    assert "REMOVE-ME" not in (output.pages[0].extract_text() or "")
    assert "KEEP-ME" in (output.pages[0].extract_text() or "")
    assert tuple(float(value) for value in output.pages[0].cropbox) == (
        10.0,
        20.0,
        602.0,
        772.0,
    )
    assert int(output.pages[0].get("/Rotate", 0)) == 90
