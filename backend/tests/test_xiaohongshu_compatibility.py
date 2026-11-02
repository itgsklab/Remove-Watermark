import json
from pathlib import Path

import pytest

from wmrm.benchmarks.xiaohongshu_compatibility import (
    XiaohongshuCompatibilityError,
    run_compatibility_audit,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "xiaohongshu_compatibility"


def test_generated_compatibility_corpus_matches_parser_contract(tmp_path: Path) -> None:
    report = run_compatibility_audit(
        FIXTURE_ROOT / "manifest.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "case_count": 5,
        "matched_expectation_count": 5,
        "mismatch_count": 0,
        "status": "pass",
    }
    encoded = (tmp_path / "report.json").read_text(encoding="utf-8")
    assert "fixture.xhscdn.com" not in encoded
    assert "Generated fixture" not in encoded
    assert "contains_live_share_links" in encoded
    assert "Status: `pass`" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_compatibility_corpus_reports_changed_expectation(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    manifest["cases"][0]["expected"]["candidate_count"] = 99
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    report = run_compatibility_audit(
        manifest_path,
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"]["status"] == "review"
    assert report["summary"]["mismatch_count"] == 1
    assert report["cases"][0]["mismatches"] == ["candidate_count: expected 99, got 2"]


def test_compatibility_corpus_requires_complete_privacy_declaration(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    manifest["privacy"]["contains_user_content"] = True
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(XiaohongshuCompatibilityError, match="privacy declaration"):
        run_compatibility_audit(
            manifest_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )
