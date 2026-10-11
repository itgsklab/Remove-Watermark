import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.photo_scene import PhotoGatedLocalizer, PhotoSceneGate
from wmrm.benchmarks.vlm_photo_gate import evaluate_photo_gate

FIXTURES = Path(__file__).parent / "fixtures" / "vlm_localization"
PHOTO_SOURCES = Path(__file__).parent / "fixtures" / "vlm_photo_sources"


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


def test_photo_source_manifest_pins_eight_independent_nasa_assets() -> None:
    manifest = json.loads((PHOTO_SOURCES / "manifest.json").read_text())

    assert manifest["schema_version"] == 1
    assert len(manifest["sources"]) == 8
    assert len({source["source_group"] for source in manifest["sources"]}) == 8
    for source in manifest["sources"]:
        path = PHOTO_SOURCES / source["file"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
        assert source["record_url"].startswith("https://images.nasa.gov/details/")
        assert source["asset_url"].startswith("https://images-assets.nasa.gov/image/")
        assert source["review_required"] is False


def test_expanded_corpus_gate_exposes_low_entropy_photo_limit(tmp_path: Path) -> None:
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
    assert summary["sample_count"] == 36
    assert summary["true_positive"] == 17
    assert summary["true_negative"] == 11
    assert summary["false_positive"] == 0
    assert summary["false_negative"] == 8
    assert summary["stable_pair_count"] == 13
    assert summary["independent_photo_source_count"] == 10
    assert summary["source_evidence_gate"] == "pass"
    assert summary["release_claim_allowed"] is False
    assert report["eligible_localization"]["precision"] == 1.0
    assert report["eligible_localization"]["recall"] == 0.769231


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
