import json
from pathlib import Path

import numpy as np
from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.photo_scene import PhotoGatedLocalizer, PhotoSceneGate
from wmrm.benchmarks.vlm_photo_gate import evaluate_photo_gate

FIXTURES = Path(__file__).parent / "fixtures" / "vlm_localization"


def test_photo_scene_gate_uses_pixel_diversity(tmp_path: Path) -> None:
    flat = tmp_path / "flat.png"
    photo_like = tmp_path / "photo-like.png"
    Image.new("RGB", (320, 240), "#e8e4dc").save(flat)
    pixels = np.random.default_rng(20261011).integers(0, 256, size=(240, 320, 3), dtype=np.uint8)
    Image.fromarray(pixels, "RGB").save(photo_like)

    gate = PhotoSceneGate()
    flat_result = gate.assess(flat)
    photo_result = gate.assess(photo_like)

    assert flat_result.eligible is False
    assert photo_result.eligible is True
    assert flat_result.luminance_entropy < photo_result.luminance_entropy
    assert flat_result.quantized_color_count < photo_result.quantized_color_count


def test_fixed_corpus_gate_reports_scope_and_source_limit(tmp_path: Path) -> None:
    predictions = json.loads((FIXTURES / "contract-predictions.json").read_text())
    predictions["detector"]["is_model_output"] = True
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text(json.dumps(predictions))

    report = evaluate_photo_gate(
        FIXTURES / "manifest.json",
        predictions_path,
        gated_predictions_path=tmp_path / "gated-predictions.json",
        localization_report_json=tmp_path / "localization.json",
        localization_report_markdown=tmp_path / "localization.md",
        gate_report_json=tmp_path / "gate.json",
        gate_report_markdown=tmp_path / "gate.md",
    )

    summary = report["summary"]
    assert summary["sample_count"] == 20
    assert summary["true_positive"] == 9
    assert summary["true_negative"] == 11
    assert summary["false_positive"] == 0
    assert summary["false_negative"] == 0
    assert summary["stable_pair_count"] == 7
    assert summary["independent_photo_source_count"] == 2
    assert summary["source_evidence_gate"] == "fail"
    assert summary["release_claim_allowed"] is False
    assert report["eligible_localization"]["precision"] == 1.0
    assert report["eligible_localization"]["recall"] == 1.0


def test_photo_gated_localizer_skips_non_photo_pixels(tmp_path: Path) -> None:
    class FakeLocalizer:
        model_id = "test/localizer"
        model_revision = "a" * 40
        runtime_metadata = {"kind": "fake"}

        def __init__(self) -> None:
            self.calls = 0

        def localize(self, image_path: Path, prompt: str):
            self.calls += 1
            return (LocalizationBox(0, 0, 10, 10, prompt, 1.0),)

    flat = tmp_path / "flat.png"
    photo_like = tmp_path / "photo-like.png"
    Image.new("RGB", (320, 240), "white").save(flat)
    pixels = np.random.default_rng(7).integers(0, 256, size=(240, 320, 3), dtype=np.uint8)
    Image.fromarray(pixels, "RGB").save(photo_like)
    inner = FakeLocalizer()
    localizer = PhotoGatedLocalizer(inner)

    assert localizer.localize(flat, "watermark") == ()
    assert localizer.localize(photo_like, "watermark")[0].label == "watermark"
    assert inner.calls == 1
    assert localizer.runtime_metadata["photo_scene_gate"]["minimum_luminance_entropy"] == 4.5
