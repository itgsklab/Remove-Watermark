import json

import numpy as np

from wmrm.benchmarks.mobile_watermark import (
    generate_mobile_cases,
    run_mobile_benchmark,
)


def test_mobile_cases_are_deterministic_and_confined_to_masks() -> None:
    first = generate_mobile_cases(seed=42)
    second = generate_mobile_cases(seed=42)
    changed_seed = generate_mobile_cases(seed=43)

    assert [item.case_id for item in first] == [
        "corner-small",
        "translucent-center",
        "multiline-overlay",
    ]
    assert all(
        np.array_equal(left.clean, right.clean)
        for left, right in zip(first, second, strict=True)
    )
    assert not np.array_equal(first[1].clean, changed_seed[1].clean)
    assert all(
        np.array_equal(item.clean[~item.mask], item.watermarked[~item.mask])
        for item in first
    )


def test_mobile_benchmark_records_quality_limits_and_artifacts(tmp_path) -> None:
    output = tmp_path / "mobile"
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    report = run_mobile_benchmark(
        output,
        report_json=json_path,
        report_markdown=markdown_path,
    )

    assert report["summary"]["status"] == "pass"
    assert report["summary"]["scenario_count"] == 3
    assert report["summary"]["outside_pixel_integrity_cases"] == 3
    assert report["summary"]["degraded_case_count"] == 1
    cases = {item["case_id"]: item for item in report["cases"]}
    assert cases["corner-small"]["actual_risk"] == "low"
    assert cases["corner-small"]["metrics"]["improvement_percent"] > 90
    assert cases["translucent-center"]["actual_risk"] == "review"
    assert cases["translucent-center"]["selection_risk"]["regions"][0][
        "low_contrast"
    ] is True
    assert cases["translucent-center"]["quality_outcome"] == "degraded"
    assert cases["multiline-overlay"]["actual_risk"] == "high"
    assert cases["multiline-overlay"]["selection_risk"]["large_selection"] is True
    assert cases["multiline-overlay"]["metrics"]["grade"] == "review"
    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert "Outside-mask integrity: 3/3" in markdown_path.read_text(encoding="utf-8")
    for case_id in cases:
        assert (output / case_id / "clean.png").is_file()
        assert (output / case_id / "watermarked.png").is_file()
        assert (output / case_id / "mask.png").is_file()
        assert (output / case_id / "result.png").is_file()
