import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from wmrm.adapters.images.florence2 import (
    Florence2ConfigurationError,
    Florence2Localizer,
    verify_model_directory,
)
from wmrm.benchmarks.vlm_fetch import fetch_pinned_model
from wmrm.benchmarks.vlm_predict import generate_predictions


class FakeRuntime:
    def predict(self, image: Image.Image, prompt: str) -> tuple[dict, ...]:
        assert image.mode == "RGB"
        assert prompt == "watermark"
        return ({"bbox": [1, 2, 10, 12], "label": "overlay"},)


class HugeBoxRuntime:
    def predict(self, image: Image.Image, prompt: str) -> tuple[dict, ...]:
        return ({"bbox": [0, 0, image.width, image.height], "label": "watermark"},)


class FakeLocalizer:
    model_id = "test/model"
    model_revision = "a" * 40

    def localize(self, image_path: Path, prompt: str):
        assert image_path.is_file()
        assert prompt == "watermark"
        return ()


def _model_fixture(tmp_path: Path) -> tuple[Path, Path]:
    model_dir = tmp_path / "model"
    model_dir.mkdir(parents=True)
    files = {}
    for name, content in {
        "model.safetensors": b"safe-weights",
        "config.json": b"{}",
    }.items():
        (model_dir / name).write_bytes(content)
        files[name] = {
            "path": name,
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    manifest = {
        "schema_version": 1,
        "model_id": "microsoft/Florence-2-base",
        "revision": "5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac",
        "allowed_files": list(files.values()),
        "runtime_policy": {
            "automatic_download": False,
            "allow_remote_code": False,
            "allow_pickle_weights": False,
            "required_weight_format": "safetensors",
            "require_exact_revision": True,
            "require_sha256_verification": True,
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return model_dir, manifest_path


def test_verified_local_model_and_injected_runtime(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    verified = verify_model_directory(model_dir, manifest_path)
    assert verified.model_id == "microsoft/Florence-2-base"

    image_path = tmp_path / "input.png"
    Image.new("RGB", (20, 20), "white").save(image_path)
    localizer = Florence2Localizer(model_dir, manifest_path, runtime=FakeRuntime())
    assert localizer.localize(image_path, "watermark")[0].label == "overlay"


def test_model_verification_rejects_modified_or_unsafe_files(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    (model_dir / "model.safetensors").write_bytes(b"changed")
    with pytest.raises(Florence2ConfigurationError, match="size mismatch"):
        verify_model_directory(model_dir, manifest_path)

    model_dir, manifest_path = _model_fixture(tmp_path / "second")
    (model_dir / "pytorch_model.bin").write_bytes(b"pickle")
    with pytest.raises(Florence2ConfigurationError, match="Forbidden"):
        verify_model_directory(model_dir, manifest_path)


def test_localizer_rejects_out_of_bounds_runtime_result(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (5, 5), "white").save(image_path)
    localizer = Florence2Localizer(model_dir, manifest_path, runtime=FakeRuntime())
    with pytest.raises(Florence2ConfigurationError, match="out-of-bounds"):
        localizer.localize(image_path, "watermark")


def test_localizer_filters_oversized_candidates(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (100, 100), "white").save(image_path)
    localizer = Florence2Localizer(model_dir, manifest_path, runtime=HugeBoxRuntime())

    assert localizer.localize(image_path, "watermark") == ()


def test_prediction_file_is_marked_as_real_model_output(tmp_path: Path) -> None:
    fixtures = Path(__file__).parent / "fixtures"
    source = fixtures / "vlm_localization" / "manifest.json"
    output = tmp_path / "predictions.json"
    result = generate_predictions(
        source,
        tmp_path / "unused-model",
        tmp_path / "unused-manifest",
        output,
        prompt="watermark",
        localizer=FakeLocalizer(),
    )
    assert result["detector"]["is_model_output"] is True
    assert len(result["predictions"]) == 20
    assert json.loads(output.read_text()) == result


def test_explicit_fetch_verifies_downloaded_files(tmp_path: Path, monkeypatch) -> None:
    source_dir, manifest_path = _model_fixture(tmp_path / "source")
    payloads = {path.name: path.read_bytes() for path in source_dir.iterdir()}

    class Response(io.BytesIO):
        def geturl(self) -> str:
            return "https://cdn-lfs.hf.co/verified"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_open(request, timeout):
        assert timeout == 60
        return Response(payloads[Path(request.full_url).name])

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    destination = tmp_path / "downloaded"

    assert fetch_pinned_model(manifest_path, destination) == destination.resolve()
    verify_model_directory(destination, manifest_path)
