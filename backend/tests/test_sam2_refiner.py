from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.sam2 import (
    Sam2MaskRefiner,
    _select_predicted_masks,
    _text_contrast_mask,
)
from wmrm.adapters.images.segmentation import SegmentationMask
from wmrm.benchmarks.mask_refinement_predict import generate_mask_predictions


class Runtime:
    metadata = {"kind": "injected", "device": "cpu"}

    def predict(self, image: Image.Image, boxes: tuple[LocalizationBox, ...]) -> np.ndarray:
        assert image.size == (8, 6)
        assert len(boxes) == 1
        return np.ones((6, 8), dtype=bool)


def test_sam2_refiner_clips_model_mask_to_candidate_boxes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "wmrm.adapters.images.sam2.audit_model_manifest",
        lambda *args, **kwargs: {"model_id": "fixture/sam2", "revision": "a" * 40},
    )
    image_path = tmp_path / "image.png"
    Image.new("RGB", (8, 6), "white").save(image_path)
    refiner = Sam2MaskRefiner(tmp_path, tmp_path / "manifest.json", runtime=Runtime())

    mask = refiner.refine(
        image_path,
        (LocalizationBox(2, 1, 6, 4, "candidate", 1.0),),
    )

    values = np.frombuffer(mask.pixels, dtype=np.uint8).reshape(6, 8)
    assert mask.selected_pixels == 12
    assert values[1:4, 2:6].all()
    assert not values[:1].any()
    assert not values[:, :2].any()


def test_multimask_selection_uses_highest_predicted_iou_per_box() -> None:
    values = np.zeros((2, 3, 4, 5), dtype=bool)
    values[0, 0, 0, 0] = True
    values[0, 2, 0, 2] = True
    values[1, 0, 1, 0] = True
    values[1, 1, 1, 1] = True
    scores = np.array([[[0.2, 0.3, 0.9], [0.1, 0.8, 0.4]]], dtype=np.float32)

    selected = _select_predicted_masks(
        values,
        scores,
        box_count=2,
        mask_selection="highest-iou",
    )

    assert selected.shape == (2, 4, 5)
    assert selected[0, 0, 2]
    assert selected[1, 1, 1]
    assert selected.sum() == 2


def test_single_mask_selection_rejects_unexpected_candidates() -> None:
    values = np.zeros((1, 2, 4, 5), dtype=bool)
    scores = np.zeros((1, 1, 2), dtype=np.float32)

    with np.testing.assert_raises_regex(RuntimeError, "single-mask mode"):
        _select_predicted_masks(
            values,
            scores,
            box_count=1,
            mask_selection="single",
        )


def test_text_contrast_mask_only_augments_text_shaped_boxes() -> None:
    pixels = np.full((20, 60, 3), 80, dtype=np.uint8)
    pixels[5:7, 8:42] = 240
    pixels[12:14, 8:42] = 10
    image = Image.fromarray(pixels, mode="RGB")

    text_mask = _text_contrast_mask(
        image,
        (LocalizationBox(4, 4, 56, 14, "candidate", 1.0),),
    )
    square_mask = _text_contrast_mask(
        image,
        (LocalizationBox(4, 2, 20, 18, "candidate", 1.0),),
    )

    assert text_mask.any()
    assert not text_mask[:4].any()
    assert not text_mask[:, :4].any()
    assert not square_mask.any()


def test_text_contrast_requires_multimask_selection(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "wmrm.adapters.images.sam2.audit_model_manifest",
        lambda *args, **kwargs: {"model_id": "fixture/sam2", "revision": "a" * 40},
    )

    with np.testing.assert_raises_regex(ValueError, "requires highest-iou"):
        Sam2MaskRefiner(
            tmp_path,
            tmp_path / "manifest.json",
            text_contrast_augmentation=True,
            runtime=Runtime(),
        )


class FakeRefiner:
    model_id = "fixture/sam2"
    model_revision = "b" * 40
    runtime_metadata = {
        "kind": "injected",
        "device": "cpu",
        "mask_selection": "highest-iou",
        "text_contrast_augmentation": True,
    }

    def refine(
        self, image_path: Path, boxes: tuple[LocalizationBox, ...]
    ) -> SegmentationMask:
        with Image.open(image_path) as image:
            width, height = image.size
        return SegmentationMask(width, height, bytes(width * height))


def test_prediction_generator_records_real_model_metadata(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    (fixture / "images").mkdir(parents=True)
    image_path = fixture / "images" / "sample.png"
    Image.new("RGB", (8, 6), "white").save(image_path)
    manifest = fixture / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "samples": [
                    {
                        "id": "sample",
                        "file": "images/sample.png",
                        "candidate_box": {"x0": 1, "y0": 1, "x1": 7, "y1": 5},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "results" / "predictions.json"

    result = generate_mask_predictions(
        manifest,
        tmp_path / "unused-model",
        tmp_path / "unused-manifest",
        output,
        refiner=FakeRefiner(),
    )

    row = result["predictions"][0]
    assert result["refiner"]["is_model_output"] is True
    assert result["refiner"]["automatic_download"] is False
    assert result["refiner"]["id"] == (
        "sam2-hiera-tiny-box-refiner-multimask-text-contrast-v1"
    )
    assert result["refiner"]["prompt_version"] == (
        "candidate-box-highest-predicted-iou-text-contrast-v1"
    )
    assert row["runtime"]["duration_ms"] > 0
    assert row["runtime"]["peak_memory_mb"] > 0
    assert row["mask_sha256"] == hashlib.sha256(
        (output.parent / row["mask_file"]).read_bytes()
    ).hexdigest()
