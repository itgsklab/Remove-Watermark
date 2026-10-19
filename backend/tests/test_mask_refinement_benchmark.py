import hashlib
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from wmrm.adapters.images.segmentation import SegmentationMask
from wmrm.benchmarks.mask_refinement import (
    MaskRefinementBenchmarkError,
    _audit_corpus_metadata,
    run_mask_refinement_benchmark,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mask_refinement"
PHOTO_FIXTURES = Path(__file__).parent / "fixtures" / "vlm_localization"


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


def test_correction_reduction_is_clamped_when_prediction_is_worse(tmp_path: Path) -> None:
    predictions, predictions_path = _copied_predictions(tmp_path)
    row = predictions["predictions"][0]
    mask_path = tmp_path / row["mask_file"]
    Image.new("L", (128, 96), 255).save(mask_path, format="PNG", optimize=False)
    row["mask_sha256"] = hashlib.sha256(mask_path.read_bytes()).hexdigest()
    predictions_path.write_text(json.dumps(predictions))

    report = _run(tmp_path, predictions_path)

    assert report["samples"][0]["correction_reduction"] == 0.0


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


def test_photo_pair_corpus_passes_provenance_and_evidence_gates(tmp_path: Path) -> None:
    report = run_mask_refinement_benchmark(
        PHOTO_FIXTURES / "mask-refinement-photo-manifest.json",
        PHOTO_FIXTURES / "mask-refinement-photo-contract-predictions.json",
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
        min_sample_count=32,
        min_negative_count=16,
        min_category_count=4,
    )

    assert report["corpus"] == {
        "kind": "provenance_photo_pairs",
        "provenance_gate": "pass",
        "pair_count": 16,
        "source_count": 16,
        "contains_user_data": False,
    }
    assert report["summary"]["sample_count"] == 32
    assert report["summary"]["negative_count"] == 16
    assert report["summary"]["category_count"] == 4
    assert report["summary"]["metric_gate"] == "pass"
    assert report["summary"]["evidence_gate"] == "pass"
    assert report["summary"]["timing_gate"] == "fail"
    assert report["summary"]["release_claim_allowed"] is False
    assert "Independent sources: 16" in (tmp_path / "report.md").read_text()


def test_photo_pair_corpus_rejects_missing_provenance() -> None:
    manifest = json.loads((PHOTO_FIXTURES / "mask-refinement-photo-manifest.json").read_text())
    del manifest["samples"][0]["usage_terms_url"]

    with pytest.raises(MaskRefinementBenchmarkError, match="usage_terms_url"):
        _audit_corpus_metadata(manifest, manifest["samples"])


def test_photo_pair_corpus_rejects_pair_metadata_mismatch() -> None:
    manifest = json.loads((PHOTO_FIXTURES / "mask-refinement-photo-manifest.json").read_text())
    pair_id = manifest["samples"][0]["pair_id"]
    pair = [sample for sample in manifest["samples"] if sample["pair_id"] == pair_id]
    pair[0]["candidate_box"] = {"x0": 0, "y0": 0, "x1": 1, "y1": 1}

    with pytest.raises(MaskRefinementBenchmarkError, match="candidate_box"):
        _audit_corpus_metadata(manifest, manifest["samples"])
