import hashlib
import json
from pathlib import Path

import pytest

from wmrm.benchmarks.pdf_redaction_corpus import (
    PdfRedactionCorpusError,
    run_corpus_audit,
)

FIXTURES = Path(__file__).parent / "fixtures" / "pdf_redaction_corpus"


def test_committed_producer_corpus_passes(tmp_path: Path) -> None:
    report = run_corpus_audit(
        FIXTURES / "manifest.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "sample_count": 3,
        "producer_count": 3,
        "cleanup_pass_count": 3,
        "mismatch_count": 0,
        "status": "pass",
    }
    assert {item["producer"] for item in report["samples"]} == {
        "Google Chrome",
        "LibreOfficeDev",
        "Microsoft Word for Mac",
    }
    assert all(item["target_removed"] for item in report["samples"])
    assert all(item["unaffected_pages_preserved"] for item in report["samples"])
    assert "| Microsoft Word for Mac |" in (tmp_path / "report.md").read_text()


def test_corpus_rejects_unreviewed_application_export(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    manifest["samples"][0]["review_required"] = True
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(PdfRedactionCorpusError, match="manually reviewed"):
        run_corpus_audit(
            path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_corpus_rejects_changed_pdf_digest(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    sample = manifest["samples"][0]
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = FIXTURES / sample["source_record"]
    (tmp_path / sample["file"]).write_bytes((FIXTURES / sample["file"]).read_bytes())
    (tmp_path / sample["source_record"]).write_bytes(source.read_bytes())
    sample["sha256"] = hashlib.sha256(b"changed").hexdigest()
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(PdfRedactionCorpusError, match="SHA-256 mismatch"):
        run_corpus_audit(
            path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )
