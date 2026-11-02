import json
from pathlib import Path

import pytest

from wmrm.benchmarks.xiaohongshu_compatibility import (
    XiaohongshuCompatibilityError,
    check_compatibility_audit,
    run_compatibility_audit,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "xiaohongshu_compatibility"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_committed_compatibility_reports_are_current() -> None:
    report = check_compatibility_audit(
        FIXTURE_ROOT / "manifest.json",
        report_json=PROJECT_ROOT / "docs/benchmarks/xiaohongshu-parser-compatibility.json",
        report_markdown=PROJECT_ROOT / "docs/benchmarks/xiaohongshu-parser-compatibility.md",
    )

    assert report["summary"]["status"] == "pass"


def test_compatibility_check_rejects_stale_report(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    run_compatibility_audit(
        FIXTURE_ROOT / "manifest.json",
        report_json=json_path,
        report_markdown=markdown_path,
    )
    markdown_path.write_text("stale\n", encoding="utf-8")

    with pytest.raises(XiaohongshuCompatibilityError, match="report.md"):
        check_compatibility_audit(
            FIXTURE_ROOT / "manifest.json",
            report_json=json_path,
            report_markdown=markdown_path,
        )


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
