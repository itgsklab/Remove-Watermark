import hashlib
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import asdict, dataclass
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from pypdf import PdfReader
from pypdf.errors import PyPdfError

LicenseMode = Literal["agpl", "commercial"]


class PdfRedactionError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PdfRedactionBackendStatus:
    backend: str
    available: bool
    version: str | None
    reason: str | None
    license_modes: tuple[str, ...] = ("agpl", "commercial")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def probe_pymupdf() -> PdfRedactionBackendStatus:
    try:
        installed_version = version("PyMuPDF")
        import_module("pymupdf")
    except (ImportError, PackageNotFoundError) as exc:
        return PdfRedactionBackendStatus(
            backend="pymupdf",
            available=False,
            version=None,
            reason=f"未安装可选依赖 PyMuPDF：{exc}",
        )
    return PdfRedactionBackendStatus(
        backend="pymupdf",
        available=True,
        version=installed_version,
        reason=None,
    )


def redact_pdf_regions(
    source_path: Path,
    output_path: Path,
    regions: list[dict[str, Any]],
    *,
    license_mode: LicenseMode,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, object]:
    """Apply transparent PDF redactions through an explicitly licensed PyMuPDF install.

    Region coordinates are crop-box-relative PDF points with a bottom-left origin. PyMuPDF
    uses an unrotated crop-box coordinate system with a top-left origin, so Y is inverted.
    """
    if license_mode not in {"agpl", "commercial"}:
        raise PdfRedactionError("必须明确选择 agpl 或 commercial 许可证模式。")
    if not regions:
        raise PdfRedactionError("区域删除计划不能为空。")
    status = probe_pymupdf()
    if not status.available:
        raise PdfRedactionError(status.reason or "PyMuPDF 后端不可用。")

    pymupdf = import_module("pymupdf")
    _raise_if_cancelled(should_cancel)
    try:
        before = PdfReader(str(source_path), strict=True)
        if before.is_encrypted:
            raise PdfRedactionError("PDF 已加密，无法处理。")
        before_geometry = [_page_geometry(page) for page in before.pages]
        grouped = _validate_and_group(regions, before_geometry)

        document = pymupdf.open(str(source_path))
        try:
            if document.needs_pass:
                raise PdfRedactionError("PDF 已加密，无法处理。")
            changed_pages: list[int] = []
            for page_number, page_regions in sorted(grouped.items()):
                _raise_if_cancelled(should_cancel)
                page = document[page_number - 1]
                page_height = before_geometry[page_number - 1][1]
                for region in page_regions:
                    rect = pymupdf.Rect(
                        float(region["x0"]),
                        page_height - float(region["y1"]),
                        float(region["x1"]),
                        page_height - float(region["y0"]),
                    )
                    page.add_redact_annot(rect, fill=False, cross_out=False)
                applied = page.apply_redactions(
                    images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                    graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
                    text=pymupdf.PDF_REDACT_TEXT_REMOVE,
                )
                if not applied:
                    raise PdfRedactionError(f"第 {page_number} 页未应用任何 redaction。")
                changed_pages.append(page_number)
            _raise_if_cancelled(should_cancel)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            document.save(str(output_path), garbage=4, clean=True, deflate=True)
        finally:
            document.close()

        _raise_if_cancelled(should_cancel)
        result = PdfReader(str(output_path), strict=True)
        if result.is_encrypted or len(result.pages) != len(before.pages):
            raise PdfRedactionError("输出 PDF 的加密状态或页数发生异常变化。")
        if [_page_geometry(page) for page in result.pages] != before_geometry:
            raise PdfRedactionError("输出 PDF 的页面尺寸或旋转发生变化。")

        return {
            "backend": "pymupdf",
            "backend_version": status.version,
            "license_mode": license_mode,
            "region_count": len(regions),
            "removed_count": len(regions),
            "changed_pages": changed_pages,
            "size_bytes": output_path.stat().st_size,
            "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        }
    except CancelledError:
        output_path.unlink(missing_ok=True)
        raise
    except (PdfRedactionError, PyPdfError, OSError, RuntimeError, TypeError, ValueError) as exc:
        output_path.unlink(missing_ok=True)
        if isinstance(exc, PdfRedactionError):
            raise
        raise PdfRedactionError(f"PDF 区域删除或校验失败：{exc}") from exc


def _validate_and_group(
    regions: list[dict[str, Any]], geometry: list[tuple[float, float, int]]
) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    seen: set[tuple[int, float, float, float, float]] = set()
    for region in regions:
        try:
            page_number = int(region["page_number"])
            x0, y0, x1, y1 = (
                float(region["x0"]),
                float(region["y0"]),
                float(region["x1"]),
                float(region["y1"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PdfRedactionError("区域缺少有效的页码或 XYXY 坐标。") from exc
        if page_number < 1 or page_number > len(geometry):
            raise PdfRedactionError("区域引用了不存在的 PDF 页面。")
        width, height, _ = geometry[page_number - 1]
        position = (page_number, x0, y0, x1, y1)
        if (
            position in seen
            or x0 < 0
            or y0 < 0
            or x1 > width
            or y1 > height
            or x0 >= x1
            or y0 >= y1
        ):
            raise PdfRedactionError("区域坐标重复、反向或超出页面 crop box。")
        seen.add(position)
        grouped[page_number].append(region)
    return grouped


def _page_geometry(page: Any) -> tuple[float, float, int]:
    return (
        float(page.cropbox.width),
        float(page.cropbox.height),
        int(page.get("/Rotate", 0)) % 360,
    )


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise CancelledError("任务已取消。")
