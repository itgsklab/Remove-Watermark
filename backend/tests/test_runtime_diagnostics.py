import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import wmrm.api.app as app_module
from wmrm.api.app import create_app
from wmrm.api.schemas import (
    OcrRuntimeDiagnostic,
    OptionalModelCapability,
    RuntimeDiagnosticsResponse,
    XiaohongshuRuntimeDiagnostic,
)
from wmrm.application.assets import AssetError
from wmrm.application.redaction_plans import _validate_ocr_languages
from wmrm.application.runtime_diagnostics import build_runtime_diagnostics
from wmrm.settings import Settings


def _disabled_vlm() -> OptionalModelCapability:
    return OptionalModelCapability(
        enabled=False,
        available=False,
        status="disabled",
        message="本地图片模型未启用；可以继续手工框选。",
    )


def test_ocr_language_validation_accepts_installed_multi_language_expression() -> None:
    assert (
        _validate_ocr_languages("chi_sim+eng", "ready", {"chi_sim", "eng", "osd"})
        == "chi_sim+eng"
    )


def test_ocr_language_validation_rejects_duplicates() -> None:
    with pytest.raises(AssetError) as raised:
        _validate_ocr_languages("eng+eng", "ready", {"eng"})

    assert raised.value.code == "OCR_LANGUAGES_DUPLICATED"


def test_runtime_diagnostics_report_languages_without_executable_or_proxy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executable = str(tmp_path / "private" / "tesseract")
    proxy = "http://user:secret@127.0.0.1:7890"
    monkeypatch.setattr(
        "wmrm.application.runtime_diagnostics.probe_tesseract",
        lambda: {"available": True, "executable": executable, "reason": None},
    )

    def fake_run(command, **kwargs):
        assert kwargs["timeout"] == 5
        if command[-1] == "--version":
            return subprocess.CompletedProcess(command, 0, stdout="tesseract 5.5.0\n", stderr="")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="List of available languages in /private/tessdata (3):\neng\nchi_sim\nosd\n",
            stderr="",
        )

    monkeypatch.setattr("wmrm.application.runtime_diagnostics.subprocess.run", fake_run)
    result = build_runtime_diagnostics(
        Settings(
            data_dir=tmp_path / "data",
            xhs_metadata_enabled=True,
            xhs_media_import_enabled=True,
            xhs_https_proxy=proxy,
        ),
        _disabled_vlm(),
    )

    assert result.ocr.status == "ready"
    assert result.ocr.version == "5.5.0"
    assert result.ocr.languages == ["chi_sim", "eng", "osd"]
    assert result.xiaohongshu.status == "ready"
    assert result.xiaohongshu.proxy_configured is True
    serialized = result.model_dump_json()
    assert executable not in serialized
    assert proxy not in serialized
    assert "secret" not in serialized


def test_runtime_diagnostics_explain_unavailable_ocr_and_invalid_xhs_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "wmrm.application.runtime_diagnostics.probe_tesseract",
        lambda: {"available": False, "executable": None, "reason": "private path"},
    )

    result = build_runtime_diagnostics(
        Settings(
            data_dir=tmp_path / "data",
            xhs_metadata_enabled=False,
            xhs_media_import_enabled=True,
        ),
        _disabled_vlm(),
    )

    assert result.ocr.status == "unavailable"
    assert result.ocr.languages == []
    assert result.xiaohongshu.status == "configuration_invalid"
    assert result.xiaohongshu.image_import_enabled is False
    assert "private path" not in result.model_dump_json()


def test_runtime_diagnostics_endpoint_uses_privacy_safe_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    response_body = RuntimeDiagnosticsResponse(
        ocr=OcrRuntimeDiagnostic(
            available=True,
            status="ready",
            version="5.5.0",
            languages=["eng"],
            message="OCR 已就绪，共检测到 1 个语言包。",
        ),
        xiaohongshu=XiaohongshuRuntimeDiagnostic(
            status="parse_only",
            metadata_reading_enabled=False,
            image_import_enabled=False,
            proxy_configured=False,
            message="当前只解析分享链接，不访问页面或下载图片。",
        ),
        vlm_localization=_disabled_vlm(),
    )
    monkeypatch.setattr(app_module, "build_runtime_diagnostics", lambda *_: response_body)
    settings = Settings(
        data_dir=tmp_path / "private-data",
        docx_preview_enabled=False,
        pdf_preview_enabled=False,
        worker_start_method="forkserver",
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/diagnostics")

    assert response.status_code == 200
    assert response.json()["schema_version"] == 1
    serialized = json.dumps(response.json())
    assert str(tmp_path) not in serialized
    assert "executable" not in serialized
    assert "proxy_url" not in serialized
