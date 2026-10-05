import json

import numpy as np

from wmrm.benchmarks.image_quality import generate_cases, run_benchmark


def test_synthetic_image_cases_are_deterministic_and_external_asset_free() -> None:
    first = generate_cases(seed=42)
    second = generate_cases(seed=42)
    changed_seed = generate_cases(seed=43)

    assert [item.case_id for item in first] == [
        "flat",
        "gradient",
        "stripes",
        "structure",
        "texture",
    ]
    assert all(
        np.array_equal(left.clean, right.clean)
        for left, right in zip(first, second, strict=True)
    )
    assert not np.array_equal(first[-1].clean, changed_seed[-1].clean)
    assert all(
        np.array_equal(item.clean[~item.mask], item.watermarked[~item.mask])
        for item in first
    )


def test_opencv_benchmark_writes_artifacts_and_reports_quality_limits(tmp_path) -> None:
    output = tmp_path / "images"
    json_path = tmp_path / "baseline.json"
    markdown_path = tmp_path / "baseline.md"

    report = run_benchmark(
        output,
        report_json=json_path,
        report_markdown=markdown_path,
    )

    assert report["summary"]["scenario_count"] == 5
    assert report["summary"]["outside_pixel_integrity_cases"] == 5
    cases = {item["case_id"]: item for item in report["cases"]}
    assert cases["flat"]["metrics"]["grade"] == "excellent"
    assert cases["gradient"]["metrics"]["grade"] == "excellent"
    assert cases["stripes"]["metrics"]["grade"] == "poor"
    assert cases["stripes"]["metrics"]["improvement_percent"] < 5
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert "Outside-mask integrity: **5/5**" in markdown_path.read_text(encoding="utf-8")
    for case_id in cases:
        assert (output / case_id / "clean.png").is_file()
        assert (output / case_id / "watermarked.png").is_file()
        assert (output / case_id / "mask.png").is_file()
        assert (output / case_id / "result.png").is_file()
