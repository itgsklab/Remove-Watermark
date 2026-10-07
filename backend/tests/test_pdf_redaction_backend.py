import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from wmrm.adapters.pdf.pymupdf_redaction import (
    PdfRedactionError,
    probe_pymupdf,
    redact_pdf_regions,
)
from wmrm.adapters.pdf.raster_inpaint import (
    PdfRasterInpaintError,
    _parse_tesseract_tsv,
    probe_tesseract,
    raster_inpaint_pdf_regions,
)
from wmrm.benchmarks.pdf_ocr_probe import run_probe as run_pdf_ocr_probe
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


def test_raster_inpaint_rebuilds_searchable_text_without_masked_word(tmp_path: Path) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())
    result = tmp_path / "result.pdf"

    report = raster_inpaint_pdf_regions(
        source,
        result,
        [{"page_number": 1, "x0": 80, "y0": 660, "x1": 235, "y1": 715}],
        license_mode="agpl",
        dpi=96,
    )

    output = PdfReader(str(result), strict=True)
    text = output.pages[0].extract_text() or ""
    assert "REMOVE-ME" not in text
    assert "KEEP-ME" in text
    assert report["rasterized_pages"] == [1]
    assert report["source_text_pages"] == [1]
    assert report["unsearchable_pages"] == []
    assert report["inserted_word_count"] == 1


def test_raster_inpaint_preserves_rotated_page_geometry(tmp_path: Path) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())
    rotated = tmp_path / "rotated.pdf"
    writer = PdfWriter(clone_from=PdfReader(str(source)))
    writer.pages[0].rotate(90)
    with rotated.open("wb") as output:
        writer.write(output)

    result = tmp_path / "result.pdf"
    raster_inpaint_pdf_regions(
        rotated,
        result,
        [{"page_number": 1, "x0": 80, "y0": 660, "x1": 235, "y1": 715}],
        license_mode="agpl",
        dpi=96,
    )

    output = PdfReader(str(result), strict=True)
    page = output.pages[0]
    text = page.extract_text() or ""
    assert int(page.get("/Rotate", 0)) == 90
    assert tuple(float(value) for value in page.mediabox) == (0.0, 0.0, 612.0, 792.0)
    assert "REMOVE-ME" not in text
    assert "KEEP-ME" in text


def test_raster_inpaint_rejects_offset_cropbox(tmp_path: Path) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())
    cropped = tmp_path / "cropped.pdf"
    writer = PdfWriter(clone_from=PdfReader(str(source)))
    writer.pages[0].cropbox.lower_left = (10, 20)
    with cropped.open("wb") as output:
        writer.write(output)

    with pytest.raises(PdfRasterInpaintError, match="crop box"):
        raster_inpaint_pdf_regions(
            cropped,
            tmp_path / "result.pdf",
            [{"page_number": 1, "x0": 1, "y0": 1, "x1": 10, "y1": 10}],
            license_mode="agpl",
        )


def test_tesseract_tsv_coordinates_are_mapped_to_pdf_points() -> None:
    payload = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\t"
        "height\tconf\ttext\n"
        "5\t1\t1\t1\t1\t1\t100\t200\t300\t80\t91.5\tSearchable\n"
    )
    words = _parse_tesseract_tsv(payload, 1000, 2000, 500, 1000)

    assert len(words) == 1
    assert (words[0].x0, words[0].y0, words[0].x1, words[0].y1) == (
        50,
        100,
        200,
        140,
    )
    assert words[0].source == "ocr"


def test_tesseract_probe_falls_back_to_known_install_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "tesseract"
    executable.write_text("")
    monkeypatch.setattr("wmrm.adapters.pdf.raster_inpaint.shutil.which", lambda _: None)
    monkeypatch.setattr(
        "wmrm.adapters.pdf.raster_inpaint._tesseract_candidates",
        lambda: (executable,),
    )

    status = probe_tesseract()

    assert status["available"] is True
    assert status["executable"] == str(executable)


def test_raster_inpaint_uses_tesseract_for_image_only_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not probe_pymupdf().available:
        pytest.skip("PyMuPDF runtime dependency is not installed")
    source = tmp_path / "image-only.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    with source.open("wb") as output:
        writer.write(output)
    executable = tmp_path / "fake-tesseract"
    executable.write_text(
        f"#!{sys.executable}\n"
        "print('level\\tpage_num\\tblock_num\\tpar_num\\tline_num\\tword_num\\tleft\\t'"
        "+ 'top\\twidth\\theight\\tconf\\ttext')\n"
        "print('5\\t1\\t1\\t1\\t1\\t1\\t20\\t30\\t100\\t20\\t95\\tOCR-WORD')\n"
    )
    executable.chmod(0o755)
    monkeypatch.setattr(
        "wmrm.adapters.pdf.raster_inpaint.shutil.which", lambda _: str(executable)
    )

    result = tmp_path / "result.pdf"
    report = raster_inpaint_pdf_regions(
        source,
        result,
        [{"page_number": 1, "x0": 1, "y0": 1, "x1": 12, "y1": 12}],
        license_mode="agpl",
        dpi=96,
    )

    assert report["ocr_pages"] == [1]
    assert report["unsearchable_pages"] == []
    assert "OCR-WORD" in (PdfReader(str(result)).pages[0].extract_text() or "")


def test_real_tesseract_pdf_ocr_probe() -> None:
    if not probe_tesseract()["available"]:
        pytest.skip("Tesseract is not installed")

    report = run_pdf_ocr_probe()

    assert report["passed"] is True
    assert report["checks"]["english_text_searchable"] is True
    assert report["checks"]["masked_text_omitted"] is True
    assert report["checks"]["masked_pixels_repaired"] is True
