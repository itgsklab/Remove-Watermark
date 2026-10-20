import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from wmrm.benchmarks.mask_refinement_gate import (
    CandidateGateError,
    apply_candidate_confirmation_gate,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    samples = []
    segmentation_rows = []
    for role, value in (("watermark_positive", 255), ("clean_negative", 255)):
        sample_id = "positive" if role == "watermark_positive" else "negative"
        image_path = tmp_path / f"{sample_id}.png"
        expected_path = tmp_path / f"{sample_id}-expected.png"
        predicted_path = tmp_path / "raw_masks" / f"{sample_id}.png"
        predicted_path.parent.mkdir(exist_ok=True)
        Image.new("RGB", (8, 8), "white").save(image_path)
        Image.new("L", (8, 8), value if role == "watermark_positive" else 0).save(expected_path)
        Image.new("L", (8, 8), value).save(predicted_path)
        samples.append(
            {
                "id": sample_id,
                "width": 8,
                "height": 8,
                "pair_role": role,
                "candidate_box": {"x0": 1, "y0": 1, "x1": 7, "y1": 7},
            }
        )
        segmentation_rows.append(
            {
                "sample_id": sample_id,
                "mask_file": f"raw_masks/{sample_id}.png",
                "mask_sha256": _sha256(predicted_path),
                "runtime": {"duration_ms": 1.0, "peak_memory_mb": 2.0},
                "workflow_seconds": None,
            }
        )

    manifest = tmp_path / "manifest.json"
    localization = tmp_path / "localization.json"
    segmentation = tmp_path / "segmentation.json"
    manifest.write_text(
        json.dumps(
            {"schema_version": 1, "corpus_kind": "provenance_photo_pairs", "samples": samples}
        )
    )
    localization.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "detector": {
                    "id": "florence2",
                    "model_id": "microsoft/Florence-2-base",
                    "model_revision": "abc123",
                    "prompt": "watermark",
                    "is_model_output": True,
                    "automatic_download": False,
                },
                "predictions": [
                    {
                        "sample_id": "positive",
                        "boxes": [{"x0": 1, "y0": 1, "x1": 7, "y1": 7}],
                    },
                    {
                        "sample_id": "negative",
                        "boxes": [{"x0": 0, "y0": 0, "x1": 1, "y1": 1}],
                    },
                ],
            }
        )
    )
    segmentation.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "refiner": {
                    "id": "sam2",
                    "model_id": "facebook/sam2-hiera-tiny",
                    "model_revision": "def456",
                    "device": "cpu",
                    "is_model_output": True,
                    "automatic_download": False,
                    "runtime": {"python": "3.12"},
                },
                "predictions": segmentation_rows,
            }
        )
    )
    return manifest, localization, segmentation


def test_gate_keeps_confirmed_positive_and_empties_rejected_negative(tmp_path: Path) -> None:
    manifest, localization, segmentation = _write_inputs(tmp_path)

    result = apply_candidate_confirmation_gate(
        manifest, localization, segmentation, tmp_path / "gated" / "predictions.json"
    )

    gate = result["refiner"]["candidate_gate"]
    assert gate["true_positive"] == 1
    assert gate["true_negative"] == 1
    assert gate["false_positive"] == 0
    assert gate["false_negative"] == 0
    assert gate["precision"] == 1.0
    assert gate["recall"] == 1.0
    positive = Image.open(tmp_path / "gated" / result["predictions"][0]["mask_file"])
    negative = Image.open(tmp_path / "gated" / result["predictions"][1]["mask_file"])
    assert positive.getbbox() == (0, 0, 8, 8)
    assert negative.getbbox() is None


def test_gate_records_below_threshold_positive_as_false_negative(tmp_path: Path) -> None:
    manifest, localization, segmentation = _write_inputs(tmp_path)
    payload = json.loads(localization.read_text())
    payload["predictions"][0]["boxes"] = [{"x0": 0, "y0": 0, "x1": 2, "y1": 2}]
    localization.write_text(json.dumps(payload))

    result = apply_candidate_confirmation_gate(
        manifest, localization, segmentation, tmp_path / "gated" / "predictions.json"
    )

    assert result["refiner"]["candidate_gate"]["false_negative"] == 1


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("localization", "is_model_output", False, "real localization"),
        ("localization", "prompt", "logo", "watermark prompt"),
        ("localization", "automatic_download", True, "must not download"),
        ("segmentation", "is_model_output", False, "real segmentation"),
        ("segmentation", "automatic_download", True, "must not download"),
    ],
)
def test_gate_rejects_untrusted_model_metadata(
    tmp_path: Path, target: str, field: str, value: object, message: str
) -> None:
    manifest, localization, segmentation = _write_inputs(tmp_path)
    path = localization if target == "localization" else segmentation
    payload = json.loads(path.read_text())
    section = "detector" if target == "localization" else "refiner"
    payload[section][field] = value
    path.write_text(json.dumps(payload))

    with pytest.raises(CandidateGateError, match=message):
        apply_candidate_confirmation_gate(
            manifest, localization, segmentation, tmp_path / "gated" / "predictions.json"
        )
