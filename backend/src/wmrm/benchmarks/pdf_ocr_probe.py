from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from wmrm.adapters.pdf.raster_inpaint import (
    probe_tesseract,
    raster_inpaint_pdf_regions,
)

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MASK = {"page_number": 1, "x0": 155, "y0": 242, "x1": 457, "y1": 352}


def run_probe(output: Path | None = None) -> dict[str, Any]:
    status = probe_tesseract()
    report: dict[str, Any] = {
        "fixture": "repository-generated synthetic image-only PDF",
        "tesseract": {"available": status["available"]},
        "checks": {},
    }
    if not status["available"]:
        report["passed"] = False
        report["reason"] = status["reason"]
        return report

    executable = str(status["executable"])
    languages = _tesseract_languages(executable)
    cjk_font = _cjk_font()
    ocr_languages = "chi_sim+eng" if cjk_font and "chi_sim" in languages else "eng"
    report["tesseract"].update(
        {
            "version": _tesseract_version(executable),
            "languages": ocr_languages,
        }
    )

    with tempfile.TemporaryDirectory(prefix="wmrm-pdf-ocr-") as directory:
        root = Path(directory)
        source = root / "source.pdf"
        result = root / "result.pdf"
        _fixture_pdf(source, cjk_font)
        pymupdf = import_module("pymupdf")
        source_document = pymupdf.open(str(source))
        try:
            source_text = "".join(page.get_text() for page in source_document)
        finally:
            source_document.close()

        operation = raster_inpaint_pdf_regions(
            source,
            result,
            [MASK],
            license_mode="agpl",
            dpi=200,
            radius=3,
            ocr_languages=ocr_languages,
        )
        operation.pop("sha256", None)
        extracted_text, cleared_pixels = _inspect_result(result)
        compact_text = "".join(extracted_text.split())
        strict_reader = PdfReader(str(result), strict=True)
        checks = {
            "source_is_image_only": not source_text.strip(),
            "ocr_page_reported": operation["ocr_pages"] == [1],
            "no_unsearchable_pages": operation["unsearchable_pages"] == [],
            "english_text_searchable": "SEARCHABLE" in extracted_text.upper(),
            "chinese_text_searchable": (
                "本地" in compact_text if ocr_languages.startswith("chi_sim") else True
            ),
            "masked_text_omitted": "REMOVE" not in extracted_text.upper(),
            "masked_pixels_repaired": cleared_pixels,
            "page_count_preserved": len(strict_reader.pages) == 1,
            "strict_reopen": True,
        }
        report.update(
            {
                "operation": operation,
                "extracted_text": extracted_text.strip(),
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(result, output)
    return report


def _fixture_pdf(path: Path, cjk_font: Path | None) -> None:
    image = Image.new("RGB", (1224, 1584), "white")
    draw = ImageDraw.Draw(image)
    latin = _font(
        [
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ],
        76,
    )
    draw.text((150, 240), "SEARCHABLE DOCUMENT", font=latin, fill="black")
    if cjk_font is not None:
        draw.text(
            (150, 430),
            "本地水印处理测试",
            font=ImageFont.truetype(str(cjk_font), 72),
            fill="black",
        )
    draw.rectangle((330, 900, 894, 1080), fill=(230, 230, 230))
    draw.text((420, 940), "REMOVE", font=latin, fill=(110, 110, 110))
    image_path = path.with_suffix(".png")
    image.save(image_path, format="PNG")

    pymupdf = import_module("pymupdf")
    document = pymupdf.open()
    try:
        page = document.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_image(page.rect, filename=str(image_path))
        document.save(str(path))
    finally:
        document.close()


def _inspect_result(path: Path) -> tuple[str, bool]:
    pymupdf = import_module("pymupdf")
    document = pymupdf.open(str(path))
    try:
        page = document[0]
        text = page.get_text()
        clip = pymupdf.Rect(
            MASK["x0"],
            PAGE_HEIGHT - MASK["y1"],
            MASK["x1"],
            PAGE_HEIGHT - MASK["y0"],
        )
        pixmap = page.get_pixmap(
            clip=clip,
            matrix=pymupdf.Matrix(2, 2),
            colorspace=pymupdf.csRGB,
            alpha=False,
        )
        pixels = np.frombuffer(pixmap.samples, dtype=np.uint8)
        cleared = float(pixels.mean()) >= 245 and int(pixels.min()) >= 225
        return text, cleared
    finally:
        document.close()


def _font(candidates: list[Path], size: int) -> ImageFont.FreeTypeFont:
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.truetype("DejaVuSans.ttf", size)


def _cjk_font() -> Path | None:
    candidates = [
        Path(
            "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/"
            "3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc"
        ),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("C:/Windows/Fonts/msyh.ttc"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def _tesseract_languages(executable: str) -> set[str]:
    completed = subprocess.run(
        [executable, "--list-langs"], capture_output=True, text=True, check=True
    )
    return {line.strip() for line in completed.stdout.splitlines()[1:] if line.strip()}


def _tesseract_version(executable: str) -> str:
    completed = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=True
    )
    return completed.stdout.splitlines()[0].strip()


def _markdown(report: dict[str, Any]) -> str:
    rows = [
        "# PDF OCR probe",
        "",
        f"- Passed: `{str(report['passed']).lower()}`",
        f"- Fixture: {report['fixture']}",
        f"- Tesseract: `{report['tesseract'].get('version', 'unavailable')}`",
        f"- Languages: `{report['tesseract'].get('languages', 'none')}`",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    rows.extend(
        f"| `{name}` | {'pass' if passed else 'fail'} |"
        for name, passed in report["checks"].items()
    )
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe real Tesseract PDF OCR reinjection")
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--output-pdf", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_probe(args.output_pdf)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(encoded, encoding="utf-8")
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(_markdown(report), encoding="utf-8")
    print(encoded, end="")
    return 1 if args.strict and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
