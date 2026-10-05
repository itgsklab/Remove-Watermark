import hashlib
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from wmrm.adapters.documents.docx_preview import (
    PreviewImage,
    PreviewResult,
    _page_number,
    _raise_if_cancelled,
    _run_command,
)


class PdfPreviewRenderer:
    def __init__(
        self,
        enabled: bool,
        dpi: int,
        max_pages: int,
        timeout_seconds: int,
    ) -> None:
        self.enabled = enabled
        self.dpi = dpi
        self.max_pages = max_pages
        self.timeout_seconds = timeout_seconds

    def render(
        self,
        source_path: Path,
        result_path: Path,
        destination: Path,
        should_cancel: Callable[[], bool] | None = None,
    ) -> PreviewResult:
        _raise_if_cancelled(should_cancel)
        if not self.enabled:
            return PreviewResult(False, warning="PDF 页面预览已关闭。")
        pdftoppm = shutil.which("pdftoppm")
        if not pdftoppm:
            return PreviewResult(False, warning="缺少 Poppler，无法生成 PDF 预览。")
        destination.mkdir(parents=True, exist_ok=True)
        try:
            images: list[PreviewImage] = []
            for side, path in (("source", source_path), ("result", result_path)):
                _raise_if_cancelled(should_cancel)
                side_root = destination / side
                side_root.mkdir(parents=True, exist_ok=True)
                raster = _run_command(
                    [
                        pdftoppm,
                        "-png",
                        "-r",
                        str(self.dpi),
                        "-f",
                        "1",
                        "-l",
                        str(self.max_pages),
                        str(path),
                        str(side_root / "page"),
                    ],
                    self.timeout_seconds,
                    should_cancel,
                )
                page_paths = sorted(side_root.glob("page-*.png"), key=_page_number)
                if raster.returncode != 0 or not page_paths:
                    detail = (raster.stderr or raster.stdout).strip()[-300:]
                    raise OSError(detail or "Poppler 未生成页面图片。")
                images.extend(self._describe(item, side) for item in page_paths)
            return PreviewResult(True, tuple(images))
        except (OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(destination, ignore_errors=True)
            return PreviewResult(False, warning=f"PDF 页面预览生成失败：{exc}")

    @staticmethod
    def _describe(path: Path, side: str) -> PreviewImage:
        return PreviewImage(
            side=side,
            page_number=_page_number(path),
            path=path,
            size_bytes=path.stat().st_size,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
