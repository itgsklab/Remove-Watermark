from __future__ import annotations

import re
import subprocess

from wmrm.adapters.pdf.raster_inpaint import probe_tesseract
from wmrm.api.schemas import (
    OcrRuntimeDiagnostic,
    OptionalModelCapability,
    RuntimeDiagnosticsResponse,
    XiaohongshuRuntimeDiagnostic,
)
from wmrm.settings import Settings

_LANGUAGE = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_VERSION = re.compile(r"(?:tesseract\s+)?([0-9][0-9A-Za-z.+_-]{0,63})", re.IGNORECASE)


def build_runtime_diagnostics(
    settings: Settings,
    vlm_capability: OptionalModelCapability,
) -> RuntimeDiagnosticsResponse:
    return RuntimeDiagnosticsResponse(
        ocr=_probe_ocr(),
        xiaohongshu=_xiaohongshu_diagnostic(settings),
        vlm_localization=vlm_capability,
    )


def _probe_ocr() -> OcrRuntimeDiagnostic:
    probe = probe_tesseract()
    executable = probe.get("executable")
    if not probe.get("available") or not isinstance(executable, str):
        return OcrRuntimeDiagnostic(
            available=False,
            status="unavailable",
            message="未检测到 Tesseract；图片型 PDF 暂时不能生成 OCR 文字层。",
        )

    try:
        version_result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        language_result = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return OcrRuntimeDiagnostic(
            available=True,
            status="probe_failed",
            message="已检测到 Tesseract，但无法读取版本或语言包列表。",
        )

    version_match = (
        _VERSION.search(version_result.stdout.splitlines()[0])
        if version_result.stdout
        else None
    )
    languages = sorted(
        {
            line.strip()
            for line in language_result.stdout.splitlines()
            if _LANGUAGE.fullmatch(line.strip())
        }
    )[:200]
    if not languages:
        return OcrRuntimeDiagnostic(
            available=True,
            status="probe_failed",
            version=version_match.group(1) if version_match else None,
            message="Tesseract 可以启动，但没有读到可用语言包。",
        )
    return OcrRuntimeDiagnostic(
        available=True,
        status="ready",
        version=version_match.group(1) if version_match else None,
        languages=languages,
        message=f"OCR 已就绪，共检测到 {len(languages)} 个语言包。",
    )


def _xiaohongshu_diagnostic(settings: Settings) -> XiaohongshuRuntimeDiagnostic:
    metadata = settings.xhs_metadata_enabled
    image_import = settings.xhs_media_import_enabled
    common = {
        "metadata_reading_enabled": metadata,
        "image_import_enabled": metadata and image_import,
        "proxy_configured": bool(settings.xhs_https_proxy),
    }
    if image_import and not metadata:
        return XiaohongshuRuntimeDiagnostic(
            status="configuration_invalid",
            message="图片导入依赖页面元数据读取，请先启用元数据读取。",
            **common,
        )
    if metadata and image_import:
        return XiaohongshuRuntimeDiagnostic(
            status="ready",
            message="分享页读取和公开图片导入均已启用。",
            **common,
        )
    if metadata:
        return XiaohongshuRuntimeDiagnostic(
            status="metadata_only",
            message="分享页元数据读取已启用，图片导入仍关闭。",
            **common,
        )
    return XiaohongshuRuntimeDiagnostic(
        status="parse_only",
        message="当前只解析分享链接，不访问页面或下载图片。",
        **common,
    )
