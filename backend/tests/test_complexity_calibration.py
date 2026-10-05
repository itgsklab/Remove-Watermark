import json
from pathlib import Path

import pytest

from wmrm.benchmarks.complexity_calibration import CalibrationError, run_calibration

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "image_complexity"


def test_real_sample_calibration_matches_expected_risks(tmp_path) -> None:
    report = run_calibration(
        FIXTURE_ROOT / "manifest.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "sample_count": 3,
        "photo_count": 2,
        "screenshot_count": 1,
        "region_count": 18,
        "matched_regions": 18,
        "mismatched_regions": 0,
        "match_rate": 1.0,
        "expected_counts": {"low": 6, "review": 6, "high": 6},
        "actual_counts": {"low": 6, "review": 6, "high": 6},
        "status": "pass",
    }
    assert (tmp_path / "report.json").is_file()
    assert "NASA, image iss074e0089803" in (tmp_path / "report.md").read_text()
    assert "green-earth-limb` (high)" in (tmp_path / "report.md").read_text()


def test_real_sample_calibration_rejects_changed_source_bytes(tmp_path) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    manifest["samples"][0]["sha256"] = "0" * 64
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    for source in FIXTURE_ROOT.glob("*.*"):
        if source.name != "manifest.json":
            (tmp_path / source.name).write_bytes(source.read_bytes())

    with pytest.raises(CalibrationError, match="SHA-256 mismatch"):
        run_calibration(
            manifest_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_real_sample_calibration_requires_independent_label_rationale(
    tmp_path: Path,
) -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text())
    manifest["samples"][0]["regions"][0].pop("label_rationale")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    for source in FIXTURE_ROOT.glob("*.*"):
        if source.name != "manifest.json":
            (tmp_path / source.name).write_bytes(source.read_bytes())

    with pytest.raises(CalibrationError, match="label_rationale"):
        run_calibration(
            manifest_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )
