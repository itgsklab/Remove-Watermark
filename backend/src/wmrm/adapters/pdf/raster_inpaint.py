from __future__ import annotations

import csv
import hashlib
import io
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from wmrm.adapters.pdf.pymupdf_redaction import (
    LicenseMode,
    _page_geometry,
    _validate_and_group,
    probe_pymupdf,
)


class PdfRasterInpaintError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SearchableWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    source: str


@dataclass(frozen=True, slots=True)
class OcrAttempt:
    words: list[SearchableWord]
    status: Literal["succeeded", "failed", "no_text"]


def probe_tesseract() -> dict[str, str | bool | None]:
    executable = shutil.which("tesseract")
    if executable is None:
        executable = next(
            (str(path) for path in _tesseract_candidates() if path.is_file()), None
        )
    if executable is None:
        return {
            "available": False,
            "executable": None,
            "reason": "未检测到 Tesseract；无原始文字层的页面将无法回灌 OCR 文本。",
        }
    return {"available": True, "executable": executable, "reason": None}


def _tesseract_candidates() -> tuple[Path, ...]:
    return (
        Path("/opt/homebrew/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
        Path("/usr/bin/tesseract"),
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    )


def raster_inpaint_pdf_regions(
    source_path: Path,
    output_path: Path,
    regions: list[dict[str, Any]],
    *,
    license_mode: LicenseMode,
    dpi: int = 144,
    radius: int = 3,
    ocr_languages: str | None = "eng",
    ocr_timeout_seconds: int = 60,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, object]:
    """Rasterize selected PDF pages, inpaint regions and restore a hidden text layer.

    Region coordinates are crop-box-relative PDF points with a bottom-left origin. Pages that
    are not selected are copied unchanged. Selected pages are rebuilt from a lossless PNG; their
    existing words are reinserted invisibly outside the masks. Image-only pages use Tesseract when
    it is available.
    """
    if license_mode not in {"agpl", "commercial"}:
        raise PdfRasterInpaintError("必须明确选择 agpl 或 commercial 许可证模式。")
    if not 96 <= dpi <= 300:
        raise PdfRasterInpaintError("PDF deep 渲染 DPI 必须在 96 到 300 之间。")
    if not 1 <= radius <= 10:
        raise PdfRasterInpaintError("OpenCV 修复半径必须在 1 到 10 之间。")
    if not regions:
        raise PdfRasterInpaintError("PDF deep 处理区域不能为空。")
    backend = probe_pymupdf()
    if not backend.available:
        raise PdfRasterInpaintError(backend.reason or "PyMuPDF 后端不可用。")

    pymupdf = import_module("pymupdf")
    tesseract = probe_tesseract()
    _raise_if_cancelled(should_cancel)
    try:
        before = PdfReader(str(source_path), strict=True)
        if before.is_encrypted:
            raise PdfRasterInpaintError("PDF 已加密，无法处理。")
        before_geometry = [_page_geometry(page) for page in before.pages]
        before_boxes = [_page_boxes(page) for page in before.pages]
        grouped = _validate_and_group(regions, before_geometry)
        source = pymupdf.open(str(source_path))
        output = pymupdf.open()
        changed_pages: list[int] = []
        source_text_pages: list[int] = []
        ocr_pages: list[int] = []
        unsearchable_pages: list[int] = []
        page_reports: list[dict[str, object]] = []
        inserted_word_count = 0
        try:
            for index in range(len(source)):
                _raise_if_cancelled(should_cancel)
                page_number = index + 1
                page_regions = grouped.get(page_number)
                if not page_regions:
                    output.insert_pdf(source, from_page=index, to_page=index)
                    continue

                page = source[index]
                original_rotation = int(page.rotation) % 360
                page.set_rotation(0)
                try:
                    width, height, _ = before_geometry[index]
                    scale = dpi / 72.0
                    pixel_count = int(round(width * scale)) * int(round(height * scale))
                    if pixel_count > 50_000_000:
                        raise PdfRasterInpaintError(
                            f"第 {page_number} 页在 {dpi} DPI 下超过 5000 万像素限制。"
                        )
                    words = _source_words(page, page_regions, height)
                    text_source = "source_text" if words else "none"
                    ocr_status = "not_needed" if words else "disabled"
                    unsearchable_reason: str | None = None
                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(scale, scale),
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )
                    original = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                        pixmap.height, pixmap.width, pixmap.n
                    )[:, :, :3]
                    mask = _pixel_mask(
                        pixmap.width,
                        pixmap.height,
                        page_regions,
                        width,
                        height,
                    )
                    repaired = cv2.inpaint(original, mask, float(radius), cv2.INPAINT_TELEA)
                    _raise_if_cancelled(should_cancel)
                    if not words and ocr_languages and tesseract["available"]:
                        ocr_attempt = _tesseract_words(
                            repaired,
                            width,
                            height,
                            str(tesseract["executable"]),
                            ocr_languages,
                            ocr_timeout_seconds,
                        )
                        words = ocr_attempt.words
                        ocr_status = ocr_attempt.status
                        if words:
                            text_source = "ocr"
                        else:
                            unsearchable_reason = (
                                "ocr_failed"
                                if ocr_attempt.status == "failed"
                                else "ocr_no_text"
                            )
                    elif not words and not ocr_languages:
                        unsearchable_reason = "ocr_disabled"
                    elif not words:
                        ocr_status = "unavailable"
                        unsearchable_reason = "ocr_unavailable"

                    image_stream = io.BytesIO()
                    Image.fromarray(repaired, mode="RGB").save(
                        image_stream, format="PNG", compress_level=6
                    )
                    media_box = page.mediabox
                    crop_box = page.cropbox
                    rebuilt = output.new_page(
                        width=float(media_box.width), height=float(media_box.height)
                    )
                    rebuilt.set_mediabox(media_box)
                    rebuilt.set_cropbox(crop_box)
                    rebuilt.insert_image(rebuilt.rect, stream=image_stream.getvalue())
                    page_word_count = _insert_hidden_words(rebuilt, words)
                    inserted_word_count += page_word_count
                    if page_word_count:
                        if text_source == "source_text":
                            source_text_pages.append(page_number)
                        elif text_source == "ocr":
                            ocr_pages.append(page_number)
                    else:
                        if words:
                            ocr_status = "failed" if text_source == "ocr" else ocr_status
                            unsearchable_reason = "text_layer_insert_failed"
                        unsearchable_pages.append(page_number)
                    page_reports.append(
                        {
                            "page_number": page_number,
                            "text_source": text_source if page_word_count else "none",
                            "ocr_status": ocr_status,
                            "word_count": page_word_count,
                            "searchable": page_word_count > 0,
                            "unsearchable_reason": unsearchable_reason,
                        }
                    )
                    rebuilt.set_rotation(original_rotation)
                    changed_pages.append(page_number)
                finally:
                    page.set_rotation(original_rotation)

            _raise_if_cancelled(should_cancel)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output.save(str(output_path), garbage=4, clean=True, deflate=True)
        finally:
            output.close()
            source.close()

        _raise_if_cancelled(should_cancel)
        result = PdfReader(str(output_path), strict=True)
        if result.is_encrypted or len(result.pages) != len(before.pages):
            raise PdfRasterInpaintError("输出 PDF 的加密状态或页数发生异常变化。")
        if [_page_geometry(page) for page in result.pages] != before_geometry:
            raise PdfRasterInpaintError("输出 PDF 的页面尺寸或旋转发生变化。")
        if [_page_boxes(page) for page in result.pages] != before_boxes:
            raise PdfRasterInpaintError("输出 PDF 的 MediaBox 或 CropBox 发生变化。")
        return {
            "backend": "pymupdf-opencv",
            "backend_version": backend.version,
            "license_mode": license_mode,
            "region_count": len(regions),
            "removed_count": len(regions),
            "changed_pages": changed_pages,
            "rasterized_pages": changed_pages,
            "source_text_pages": source_text_pages,
            "ocr_pages": ocr_pages,
            "unsearchable_pages": unsearchable_pages,
            "page_reports": page_reports,
            "inserted_word_count": inserted_word_count,
            "dpi": dpi,
            "radius": radius,
            "size_bytes": output_path.stat().st_size,
            "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        }
    except CancelledError:
        output_path.unlink(missing_ok=True)
        raise
    except (
        PdfRasterInpaintError,
        PyPdfError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ) as exc:
        output_path.unlink(missing_ok=True)
        if isinstance(exc, PdfRasterInpaintError):
            raise
        raise PdfRasterInpaintError(f"PDF deep 修复或校验失败：{exc}") from exc


def _source_words(
    page: Any, regions: list[dict[str, Any]], page_height: float
) -> list[SearchableWord]:
    masks = [
        (
            float(item["x0"]),
            page_height - float(item["y1"]),
            float(item["x1"]),
            page_height - float(item["y0"]),
        )
        for item in regions
    ]
    words = []
    for item in page.get_text("words", sort=True):
        x0, y0, x1, y1, text = item[:5]
        if not str(text).strip() or any(_intersects((x0, y0, x1, y1), mask) for mask in masks):
            continue
        words.append(
            SearchableWord(
                float(x0), float(y0), float(x1), float(y1), str(text), "source"
            )
        )
    return words


def _page_boxes(page: Any) -> tuple[tuple[float, ...], tuple[float, ...]]:
    return (
        tuple(float(value) for value in page.mediabox),
        tuple(float(value) for value in page.cropbox),
    )


def _pixel_mask(
    pixel_width: int,
    pixel_height: int,
    regions: list[dict[str, Any]],
    page_width: float,
    page_height: float,
) -> np.ndarray:
    mask = np.zeros((pixel_height, pixel_width), dtype=np.uint8)
    for item in regions:
        x0 = max(0, int(np.floor(float(item["x0"]) / page_width * pixel_width)))
        x1 = min(pixel_width, int(np.ceil(float(item["x1"]) / page_width * pixel_width)))
        y0 = max(
            0,
            int(np.floor((page_height - float(item["y1"])) / page_height * pixel_height)),
        )
        y1 = min(
            pixel_height,
            int(np.ceil((page_height - float(item["y0"])) / page_height * pixel_height)),
        )
        if x0 >= x1 or y0 >= y1:
            raise PdfRasterInpaintError("区域转换为渲染像素后为空。")
        mask[y0:y1, x0:x1] = 255
    return mask


def _tesseract_words(
    image: np.ndarray,
    page_width: float,
    page_height: float,
    executable: str,
    languages: str,
    timeout_seconds: int,
) -> OcrAttempt:
    with tempfile.TemporaryDirectory(prefix="wmrm-pdf-ocr-") as temporary:
        image_path = Path(temporary) / "page.png"
        Image.fromarray(image, mode="RGB").save(image_path, format="PNG")
        try:
            completed = subprocess.run(
                [executable, str(image_path), "stdout", "-l", languages, "tsv"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return OcrAttempt([], "failed")
    if completed.returncode != 0:
        return OcrAttempt([], "failed")
    words = _parse_tesseract_tsv(
        completed.stdout,
        image.shape[1],
        image.shape[0],
        page_width,
        page_height,
    )
    return OcrAttempt(words, "succeeded" if words else "no_text")


def _parse_tesseract_tsv(
    payload: str,
    pixel_width: int,
    pixel_height: int,
    page_width: float,
    page_height: float,
) -> list[SearchableWord]:
    words = []
    for row in csv.DictReader(io.StringIO(payload), delimiter="\t"):
        try:
            text = row["text"].strip()
            confidence = float(row["conf"])
            left = float(row["left"])
            top = float(row["top"])
            width = float(row["width"])
            height = float(row["height"])
        except (KeyError, TypeError, ValueError):
            continue
        if not text or confidence < 30 or width <= 0 or height <= 0:
            continue
        words.append(
            SearchableWord(
                left / pixel_width * page_width,
                top / pixel_height * page_height,
                (left + width) / pixel_width * page_width,
                (top + height) / pixel_height * page_height,
                text,
                "ocr",
            )
        )
    return words


def _insert_hidden_words(page: Any, words: list[SearchableWord]) -> int:
    inserted = 0
    for word in words:
        font_name = "china-s" if any(ord(character) > 255 for character in word.text) else "helv"
        font_size = max(3.0, min(72.0, (word.y1 - word.y0) * 0.8))
        try:
            page.insert_text(
                (word.x0, word.y1),
                word.text,
                fontsize=font_size,
                fontname=font_name,
                render_mode=3,
                overlay=True,
            )
        except (RuntimeError, ValueError):
            continue
        inserted += 1
    return inserted


def _intersects(first: tuple[float, ...], second: tuple[float, ...]) -> bool:
    return min(first[2], second[2]) > max(first[0], second[0]) and min(
        first[3], second[3]
    ) > max(first[1], second[1])


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise CancelledError("任务已取消。")
