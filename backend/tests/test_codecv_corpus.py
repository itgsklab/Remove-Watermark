import json
from pathlib import Path

import pytest

from wmrm.benchmarks.codecv_corpus import CodeCvCorpusError, run_corpus_audit
from wmrm.benchmarks.codecv_probe import probe_export

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "codecv_corpus"


def test_generated_codecv_corpus_validates_detection_and_cleanup(tmp_path) -> None:
    report = run_corpus_audit(
        FIXTURE_ROOT / "manifest.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "sample_count": 3,
        "generated_count": 3,
        "real_export_count": 0,
        "matched_source_count": 2,
        "cleanup_attempt_count": 2,
        "cleanup_pass_count": 2,
        "mismatch_count": 0,
        "status": "generated_only",
    }
    assert all(not sample["mismatches"] for sample in report["samples"])
    assert "must not be treated as template compatibility evidence" in (
        tmp_path / "report.md"
    ).read_text()


def test_codecv_corpus_rejects_changed_source_bytes(tmp_path) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    manifest["samples"][0]["sha256"] = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    for source in FIXTURE_ROOT.glob("*.pdf"):
        (tmp_path / source.name).write_bytes(source.read_bytes())

    with pytest.raises(CodeCvCorpusError, match="SHA-256 mismatch"):
        run_corpus_audit(
            manifest_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_codecv_corpus_can_require_real_exports(tmp_path) -> None:
    with pytest.raises(CodeCvCorpusError, match="requires at least one"):
        run_corpus_audit(
            FIXTURE_ROOT / "manifest.json",
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
            require_real=True,
        )


def test_codecv_corpus_requires_manual_review_for_real_exports(tmp_path) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    manifest["samples"][0]["provenance"] = "private_export"
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    for source in FIXTURE_ROOT.glob("*.pdf"):
        (tmp_path / source.name).write_bytes(source.read_bytes())

    with pytest.raises(CodeCvCorpusError, match="review_required to false"):
        run_corpus_audit(
            manifest_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_codecv_probe_creates_review_required_manifest_entry() -> None:
    result = probe_export(
        FIXTURE_ROOT / "generated-gs-evenodd-v2.pdf",
        sample_id="local-template-export",
        template_version="review-me",
        provenance="private_export",
    )

    assert result["review_required"] is True
    assert result["expected"]["match_status"] == "matched"
    assert result["expected"]["candidate_count"] == 2
    assert result["expected"]["candidate_pages"] == [1, 2]
    assert result["observed_resources"] == ["/TileP7"]
