import subprocess
from pathlib import Path

from wmrm.adapters.pdf.preview import PdfPreviewRenderer


def test_pdf_preview_can_be_disabled(tmp_path: Path) -> None:
    renderer = PdfPreviewRenderer(enabled=False, dpi=110, max_pages=8, timeout_seconds=30)

    result = renderer.render(
        tmp_path / "source.pdf",
        tmp_path / "result.pdf",
        tmp_path / "preview",
    )

    assert result.available is False
    assert result.warning == "PDF 页面预览已关闭。"


def test_pdf_preview_reports_missing_poppler(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("wmrm.adapters.pdf.preview.shutil.which", lambda _: None)
    renderer = PdfPreviewRenderer(enabled=True, dpi=110, max_pages=8, timeout_seconds=30)

    result = renderer.render(
        tmp_path / "source.pdf",
        tmp_path / "result.pdf",
        tmp_path / "preview",
    )

    assert result.available is False
    assert result.warning == "缺少 Poppler，无法生成 PDF 预览。"


def test_pdf_preview_records_both_sides(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("wmrm.adapters.pdf.preview.shutil.which", lambda _: "pdftoppm")

    def fake_run(command, timeout_seconds, should_cancel):
        prefix = Path(command[-1])
        prefix.parent.mkdir(parents=True, exist_ok=True)
        prefix.with_name(prefix.name + "-1.png").write_bytes(b"fake-png")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("wmrm.adapters.pdf.preview._run_command", fake_run)
    renderer = PdfPreviewRenderer(enabled=True, dpi=110, max_pages=8, timeout_seconds=30)

    result = renderer.render(
        tmp_path / "source.pdf",
        tmp_path / "result.pdf",
        tmp_path / "preview",
    )

    assert result.available is True
    assert [(item.side, item.page_number) for item in result.images] == [
        ("source", 1),
        ("result", 1),
    ]
