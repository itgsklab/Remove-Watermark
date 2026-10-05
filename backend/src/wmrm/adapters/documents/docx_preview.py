import hashlib
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import CancelledError
from dataclasses import dataclass
from pathlib import Path


class DocxPreviewError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PreviewImage:
    side: str
    page_number: int
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class PreviewResult:
    available: bool
    images: tuple[PreviewImage, ...] = ()
    warning: str | None = None


class DocxPreviewRenderer:
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
            return PreviewResult(False, warning="DOCX 页面预览已关闭。")
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        pdftoppm = shutil.which("pdftoppm")
        if not soffice or not pdftoppm:
            return PreviewResult(False, warning="缺少 LibreOffice 或 Poppler，无法生成预览。")

        destination.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="wmrm-preview-") as temporary:
                work_root = Path(temporary)
                images: list[PreviewImage] = []
                images.extend(
                    self._render_side(
                        soffice, pdftoppm, source_path, "source", work_root, should_cancel
                    )
                )
                images.extend(
                    self._render_side(
                        soffice, pdftoppm, result_path, "result", work_root, should_cancel
                    )
                )
                for image in images:
                    _raise_if_cancelled(should_cancel)
                    target = destination / image.side / f"page-{image.page_number}.png"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(image.path, target)
                stored = tuple(self._describe(path) for path in sorted(destination.glob("*/*.png")))
                return PreviewResult(True, stored)
        except (DocxPreviewError, OSError, subprocess.SubprocessError) as exc:
            shutil.rmtree(destination, ignore_errors=True)
            return PreviewResult(False, warning=f"页面预览生成失败：{exc}")

    def _render_side(
        self,
        soffice: str,
        pdftoppm: str,
        source_path: Path,
        side: str,
        work_root: Path,
        should_cancel: Callable[[], bool] | None,
    ) -> list[PreviewImage]:
        side_root = work_root / side
        input_root = side_root / "input"
        pdf_root = side_root / "pdf"
        image_root = side_root / "images"
        profile_root = side_root / "profile"
        input_root.mkdir(parents=True)
        pdf_root.mkdir()
        image_root.mkdir()
        profile_root.mkdir()
        docx_path = input_root / f"{side}.docx"
        shutil.copyfile(source_path, docx_path)
        conversion = _run_command(
            [
                soffice,
                "--headless",
                "--nologo",
                "--nodefault",
                "--nolockcheck",
                "--nofirststartwizard",
                f"-env:UserInstallation={profile_root.as_uri()}",
                "--convert-to",
                "pdf",
                "--outdir",
                str(pdf_root),
                str(docx_path),
            ],
            self.timeout_seconds,
            should_cancel,
        )
        pdf_path = pdf_root / f"{side}.pdf"
        if conversion.returncode != 0 or not pdf_path.is_file():
            detail = (conversion.stderr or conversion.stdout).strip()[-300:]
            raise DocxPreviewError(detail or "LibreOffice 未生成 PDF。")
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
                str(pdf_path),
                str(image_root / "page"),
            ],
            self.timeout_seconds,
            should_cancel,
        )
        page_paths = sorted(image_root.glob("page-*.png"), key=_page_number)
        if raster.returncode != 0 or not page_paths:
            detail = (raster.stderr or raster.stdout).strip()[-300:]
            raise DocxPreviewError(detail or "Poppler 未生成页面图片。")
        return [self._describe(path, side) for path in page_paths]

    def _describe(self, path: Path, side: str | None = None) -> PreviewImage:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return PreviewImage(
            side=side or path.parent.name,
            page_number=_page_number(path),
            path=path,
            size_bytes=path.stat().st_size,
            sha256=digest,
        )


def _page_number(path: Path) -> int:
    try:
        return int(path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError) as exc:
        raise DocxPreviewError(f"无法识别预览页码：{path.name}") from exc


def _run_command(
    command: list[str],
    timeout_seconds: int,
    should_cancel: Callable[[], bool] | None,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None:
        if should_cancel is not None and should_cancel():
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise CancelledError("任务已取消。")
        if time.monotonic() >= deadline:
            process.kill()
            stdout, stderr = process.communicate()
            raise subprocess.TimeoutExpired(command, timeout_seconds, stdout, stderr)
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise CancelledError("任务已取消。")
