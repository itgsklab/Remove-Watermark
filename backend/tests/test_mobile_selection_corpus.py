import json
from pathlib import Path

import pytest

from wmrm.benchmarks.mobile_selection_corpus import (
    MobileSelectionCorpusError,
    run_corpus_audit,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mobile_selection_corpus"


def test_mobile_selection_corpus_matches_reviewed_expectations(tmp_path: Path) -> None:
    report = run_corpus_audit(
        FIXTURES / "manifest.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "sample_count": 3,
        "low_contrast_count": 1,
        "large_selection_count": 1,
        "mismatch_count": 0,
        "status": "pass",
    }
    samples = {item["id"]: item for item in report["samples"]}
    assert samples["real-horizon-translucent"]["actual_low_contrast"] is True
    assert samples["real-night-multiline"]["actual_large_selection"] is True
    assert "Portrait crops" in (tmp_path / "report.md").read_text()


def test_mobile_selection_corpus_rejects_changed_derived_digest(
    tmp_path: Path,
) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    copied_sources: set[str] = set()
    for sample in manifest["samples"]:
        (tmp_path / sample["file"]).write_bytes((FIXTURES / sample["file"]).read_bytes())
        source = (FIXTURES / sample["source_file"]).resolve()
        if source.name not in copied_sources:
            (source_dir / source.name).write_bytes(source.read_bytes())
            copied_sources.add(source.name)
        sample["source_file"] = f"source/{source.name}"
    manifest["samples"][0]["sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(MobileSelectionCorpusError, match="SHA-256 mismatch"):
        run_corpus_audit(
            path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_mobile_selection_corpus_requires_manual_review(tmp_path: Path) -> None:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    manifest["samples"][0]["review_required"] = True
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(MobileSelectionCorpusError, match="manually reviewed"):
        run_corpus_audit(
            path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )
