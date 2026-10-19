import hashlib
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from wmrm.adapters.images.segmentation import SegmentationMask
from wmrm.benchmarks.mask_refinement import (
    MaskRefinementBenchmarkError,
    run_mask_refinement_benchmark,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mask_refinement"


def _copied_predictions(tmp_path: Path) -> tuple[dict, Path]:
    shutil.copytree(FIXTURES / "predicted", tmp_path / "predicted")
    predictions = json.loads((FIXTURES / "contract-predictions.json").read_text())
    path = tmp_path / "predictions.json"
    return predictions, path


def _run(tmp_path: Path, predictions_path: Path | None = None, **kwargs):
    return run_mask_refinement_benchmark(
        FIXTURES / "manifest.json",
        predictions_path or FIXTURES / "contract-predictions.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
        **kwargs,
    )


def test_segmentation_mask_contract_is_immutable_and_binary() -> None:
    mask = SegmentationMask(2, 2, bytes((0, 1, 1, 0)))

    assert mask.selected_pixels == 2
    with pytest.raises(ValueError, match="pixel count"):
        SegmentationMask(2, 2, bytes((0, 1)))
    with pytest.raises(ValueError, match="binary"):
        SegmentationMask(2, 2, bytes((0, 1, 2, 0)))


def test_contract_fixture_scores_masks_and_correction_workload(tmp_path: Path) -> None:
    report = _run(tmp_path)

    assert report["evaluation_kind"] == "contract_fixture"
    assert report["summary"] == {
        "sample_count": 8,
        "positive_count": 4,
        "negative_count": 4,
        "category_count": 8,
        "true_positive_pixels": 1560,
        "false_positive_pixels": 0,
        "false_negative_pixels": 0,
        "candidate_correction_pixels": 14818,
        "refined_correction_pixels": 0,
        "outside_candidate_pixels": 0,
        "precision": 1.0,
        "recall": 1.0,
        "iou": 1.0,
        "correction_reduction": 1.0,
        "timing_evidence_count": 0,
        "metric_gate": "pass",
        "evidence_gate": "pass",
        "timing_gate": "fail",
        "release_claim_allowed": False,
    }
    markdown = (tmp_path / "report.md").read_text()
    assert "not a model performance result" in markdown
    assert "Timing gate: **fail**" in markdown


def test_contract_fixture_cannot_satisfy_model_requirement(tmp_path: Path) -> None:
    with pytest.raises(MaskRefinementBenchmarkError, match="real model output"):
        _run(tmp_path, require_model_output=True)


def test_benchmark_rejects_automatic_weight_download(tmp_path: Path) -> None:
    predictions, predictions_path = _copied_predictions(tmp_path)
    predictions["refiner"]["automatic_download"] = True
    predictions_path.write_text(json.dumps(predictions))

    with pytest.raises(MaskRefinementBenchmarkError, match="must not download automatically"):
        _run(tmp_path, predictions_path)


def test_outside_candidate_pixel_fails_metric_gate(tmp_path: Path) -> None:
    predictions, predictions_path = _copied_predictions(tmp_path)
    row = predictions["predictions"][0]
    mask_path = tmp_path / row["mask_file"]
    with Image.open(mask_path) as source:
        mask = source.copy()
    mask.putpixel((0, 0), 255)
    mask.save(mask_path, format="PNG", optimize=False)
    row["mask_sha256"] = hashlib.sha256(mask_path.read_bytes()).hexdigest()
    predictions_path.write_text(json.dumps(predictions))

    report = _run(tmp_path, predictions_path)

    assert report["summary"]["outside_candidate_pixels"] == 1
    assert report["summary"]["metric_gate"] == "fail"


def test_prediction_mask_digest_is_verified(tmp_path: Path) -> None:
    predictions, predictions_path = _copied_predictions(tmp_path)
    predictions["predictions"][0]["mask_sha256"] = "0" * 64
    predictions_path.write_text(json.dumps(predictions))

    with pytest.raises(MaskRefinementBenchmarkError, match="SHA-256 mismatch"):
        _run(tmp_path, predictions_path)


def test_release_claim_requires_model_runtime_and_human_timing(tmp_path: Path) -> None:
    predictions, predictions_path = _copied_predictions(tmp_path)
    predictions["refiner"].update(
        {
            "is_model_output": True,
            "model_id": "example/local-mask-refiner",
            "model_revision": "0123456789abcdef",
            "device": "cpu",
        }
    )
    for row in predictions["predictions"]:
        row["runtime"] = {"duration_ms": 25.0, "peak_memory_mb": 128.0}
        row["workflow_seconds"] = {"manual": 60.0, "box": 40.0, "refined": 20.0}
    predictions_path.write_text(json.dumps(predictions))

    report = _run(tmp_path, predictions_path, require_model_output=True)

    assert report["summary"]["metric_gate"] == "pass"
    assert report["summary"]["evidence_gate"] == "pass"
    assert report["summary"]["timing_gate"] == "pass"
    assert report["summary"]["release_claim_allowed"] is True
    assert report["workflow_timing"] == {
        "count": 8,
        "manual_mean": 60.0,
        "box_mean": 40.0,
        "refined_mean": 20.0,
    }
