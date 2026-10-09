import hashlib
import json
from pathlib import Path

import pytest

from wmrm.adapters.images.detection import LocalizationBox, intersection_over_union
from wmrm.benchmarks.vlm_localization import (
    LocalizationBenchmarkError,
    run_localization_benchmark,
)

FIXTURES = Path(__file__).parent / "fixtures" / "vlm_localization"
MODEL_MANIFEST = Path(__file__).parents[2] / "docs" / "models" / "florence-2-base.json"


def test_localization_box_and_iou_contract() -> None:
    expected = LocalizationBox(0, 0, 10, 10, "watermark", 1)
    predicted = LocalizationBox(5, 0, 15, 10, "watermark", 0.8)

    assert intersection_over_union(expected, predicted) == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="positive"):
        LocalizationBox(5, 0, 5, 10, "watermark", 0.8)
    with pytest.raises(ValueError, match="between 0 and 1"):
        LocalizationBox(0, 0, 10, 10, "watermark", 1.1)


def test_florence_model_manifest_keeps_weights_optional_and_safe() -> None:
    manifest = json.loads(MODEL_MANIFEST.read_text())

    assert manifest["model_id"] == "microsoft/Florence-2-base"
    assert len(manifest["revision"]) == 40
    assert manifest["license"]["spdx"] == "MIT"
    files = {item["path"]: item for item in manifest["allowed_files"]}
    assert files["model.safetensors"]["size_bytes"] == 463_221_266
    assert len(files["model.safetensors"]["sha256"]) == 64
    assert "pytorch_model.bin" not in files
    assert manifest["runtime_policy"] == {
        "bundled_in_release": False,
        "automatic_download": False,
        "allow_remote_code": False,
        "allow_pickle_weights": False,
        "required_weight_format": "safetensors",
        "require_exact_revision": True,
        "require_sha256_verification": True,
    }
    vendor_root = Path(__file__).parents[1] / "src" / "wmrm" / "vendor" / "florence2"
    implementation = manifest["runtime_implementation"]
    assert implementation["license"] == "Apache-2.0"
    for record in implementation["vendored_files"]:
        assert hashlib.sha256((vendor_root / record["path"]).read_bytes()).hexdigest() == record[
            "sha256"
        ]


def test_contract_fixture_scores_positive_and_negative_samples(tmp_path: Path) -> None:
    report = run_localization_benchmark(
        FIXTURES / "manifest.json",
        FIXTURES / "contract-predictions.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["evaluation_kind"] == "contract_fixture"
    assert report["summary"]["sample_count"] == 5
    assert report["summary"]["positive_count"] == 3
    assert report["summary"]["negative_count"] == 2
    assert report["summary"]["true_positive"] == 3
    assert report["summary"]["false_positive"] == 0
    assert report["summary"]["false_negative"] == 0
    assert report["summary"]["metric_gate"] == "pass"
    assert report["summary"]["release_claim_allowed"] is False
    assert "not a model performance result" in (tmp_path / "report.md").read_text()


def test_contract_fixture_cannot_satisfy_real_model_requirement(tmp_path: Path) -> None:
    with pytest.raises(LocalizationBenchmarkError, match="real model output"):
        run_localization_benchmark(
            FIXTURES / "manifest.json",
            FIXTURES / "contract-predictions.json",
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
            require_model_output=True,
        )


def test_benchmark_rejects_out_of_bounds_prediction(tmp_path: Path) -> None:
    predictions = json.loads((FIXTURES / "contract-predictions.json").read_text())
    predictions["predictions"][0]["boxes"][0]["x1"] = 5_000
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps(predictions))

    with pytest.raises(LocalizationBenchmarkError, match="image bounds"):
        run_localization_benchmark(
            FIXTURES / "manifest.json",
            predictions_path,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_benchmark_counts_negative_false_positive(tmp_path: Path) -> None:
    predictions = json.loads((FIXTURES / "contract-predictions.json").read_text())
    predictions["predictions"][3]["boxes"] = [
        {
            "x0": 10,
            "y0": 10,
            "x1": 100,
            "y1": 100,
            "label": "watermark",
            "confidence": 0.7,
        }
    ]
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps(predictions))

    report = run_localization_benchmark(
        FIXTURES / "manifest.json",
        predictions_path,
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"]["false_positive"] == 1
    assert report["summary"]["precision"] == 0.75


def test_zero_recall_has_zero_f1(tmp_path: Path) -> None:
    predictions = json.loads((FIXTURES / "contract-predictions.json").read_text())
    for row in predictions["predictions"]:
        row["boxes"] = []
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps(predictions))

    report = run_localization_benchmark(
        FIXTURES / "manifest.json",
        predictions_path,
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"]["precision"] == 1.0
    assert report["summary"]["recall"] == 0.0
    assert report["summary"]["f1"] == 0.0
