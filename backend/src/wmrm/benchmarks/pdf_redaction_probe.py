import argparse
import json
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

from wmrm.adapters.pdf.pymupdf_redaction import probe_pymupdf, redact_pdf_regions


def run_probe(output: Path | None = None) -> dict[str, Any]:
    status = probe_pymupdf()
    report: dict[str, Any] = {"status": status.to_dict(), "checks": {}}
    if not status.available:
        report["passed"] = False
        return report

    with tempfile.TemporaryDirectory(prefix="wmrm-redaction-") as directory:
        root = Path(directory)
        source = root / "source.pdf"
        result = root / "result.pdf"
        source.write_bytes(_fixture_pdf())
        operation = redact_pdf_regions(
            source,
            result,
            [{"page_number": 1, "x0": 90, "y0": 680, "x1": 245, "y1": 735}],
            license_mode="agpl",
        )
        pdf = PdfReader(str(result), strict=True)
        text_page_one = pdf.pages[0].extract_text() or ""
        text_page_two = pdf.pages[1].extract_text() or ""
        annotations = pdf.pages[0].get("/Annots", [])
        pymupdf = __import__("pymupdf")
        rendered = pymupdf.open(str(result))
        try:
            page = rendered[0]
            clip = pymupdf.Rect(90, 792 - 735, 245, 792 - 680)
            pixmap = page.get_pixmap(clip=clip, colorspace=pymupdf.csRGB, alpha=False)
            cleared_pixels = all(value >= 245 for value in pixmap.samples)
            vector_graphics_removed = not page.get_drawings()
        finally:
            rendered.close()
        checks = {
            "target_text_removed": "REMOVE-ME" not in text_page_one,
            "outside_text_preserved": "KEEP-ME" in text_page_one,
            "unaffected_page_preserved": "PAGE-TWO" in text_page_two,
            "redacted_image_pixels_cleared": cleared_pixels,
            "overlapping_vector_removed": vector_graphics_removed,
            "overlapping_link_removed": len(annotations) == 0,
            "page_count_preserved": len(pdf.pages) == 2,
            "strict_reopen": True,
        }
        report.update({"operation": operation, "checks": checks, "passed": all(checks.values())})
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(result.read_bytes())
    return report


def _fixture_pdf() -> bytes:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    image = DecodedStreamObject()
    image.set_data(b"\x11\x22\x33")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)
    for index in range(2):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
                NameObject("/XObject"): DictionaryObject(
                    {NameObject("/Im1"): image_ref}
                ),
            }
        )
        stream = DecodedStreamObject()
        content = (
            b"BT /F1 20 Tf 100 700 Td (REMOVE-ME) Tj ET "
            b"BT /F1 20 Tf 320 700 Td (KEEP-ME) Tj ET "
            b"0 0 1 rg 95 685 155 45 re f "
            b"q 40 0 0 40 180 687 cm /Im1 Do Q"
            if index == 0
            else b"BT /F1 20 Tf 100 700 Td (PAGE-TWO) Tj ET"
        )
        stream.set_data(content)
        page[NameObject("/Contents")] = writer._add_object(stream)
        if index == 0:
            link = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/Rect"): ArrayObject(
                        [FloatObject(100), FloatObject(690), FloatObject(230), FloatObject(725)]
                    ),
                    NameObject("/A"): DictionaryObject(
                        {
                            NameObject("/S"): NameObject("/URI"),
                            NameObject("/URI"): TextStringObject("https://example.com"),
                        }
                    ),
                }
            )
            page[NameObject("/Annots")] = ArrayObject([writer._add_object(link)])
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe optional PyMuPDF redaction semantics")
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--output-pdf", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_probe(args.output_pdf)
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
