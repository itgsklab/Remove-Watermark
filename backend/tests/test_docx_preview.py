from pathlib import Path

from wmrm.adapters.documents.docx_preview import DocxPreviewRenderer


def test_preview_can_be_disabled(tmp_path: Path) -> None:
    renderer = DocxPreviewRenderer(enabled=False, dpi=110, max_pages=8, timeout_seconds=30)

    result = renderer.render(
        tmp_path / "source.docx",
        tmp_path / "result.docx",
        tmp_path / "preview",
    )

    assert result.available is False
    assert result.images == ()
    assert result.warning == "DOCX 页面预览已关闭。"


def test_preview_reports_missing_render_commands(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("wmrm.adapters.documents.docx_preview.shutil.which", lambda _: None)
    renderer = DocxPreviewRenderer(enabled=True, dpi=110, max_pages=8, timeout_seconds=30)

    result = renderer.render(
        tmp_path / "source.docx",
        tmp_path / "result.docx",
        tmp_path / "preview",
    )

    assert result.available is False
    assert result.warning == "缺少 LibreOffice 或 Poppler，无法生成预览。"
