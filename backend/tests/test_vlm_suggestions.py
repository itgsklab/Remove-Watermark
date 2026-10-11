import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.api.app import create_app
from wmrm.settings import Settings


class FakeLocalizer:
    model_id = "test/local-model"
    model_revision = "a" * 40
    runtime_metadata = {"kind": "fake"}

    def localize(self, image_path: Path, prompt: str):
        assert image_path.is_file()
        assert prompt == "watermark"
        return (LocalizationBox(5, 7, 25, 18, "watermark", 1.0),)


def _model_fixture(tmp_path: Path) -> tuple[Path, Path]:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    weights = b"reviewed-safe-weights"
    (model_dir / "model.safetensors").write_bytes(weights)
    manifest = {
        "schema_version": 1,
        "model_id": "test/local-model",
        "revision": "a" * 40,
        "allowed_files": [
            {
                "path": "model.safetensors",
                "size_bytes": len(weights),
                "sha256": hashlib.sha256(weights).hexdigest(),
            }
        ],
        "runtime_policy": {
            "automatic_download": False,
            "allow_remote_code": False,
            "allow_pickle_weights": False,
            "required_weight_format": "safetensors",
            "require_exact_revision": True,
            "require_sha256_verification": True,
        },
    }
    manifest_path = tmp_path / "model-manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return model_dir, manifest_path


def _image_bytes(*, photo_like: bool) -> bytes:
    output = BytesIO()
    if photo_like:
        pixels = np.random.default_rng(7).integers(0, 256, (48, 64, 3), dtype=np.uint8)
        image = Image.fromarray(pixels, "RGB")
    else:
        image = Image.new("RGB", (64, 48), "white")
    image.save(output, format="PNG")
    return output.getvalue()


def _upload_and_analyze(client: TestClient, payload: bytes) -> tuple[dict, dict]:
    asset = client.post(
        "/api/v1/assets", files={"file": ("photo.png", payload, "image/png")}
    ).json()
    analysis = client.post(
        "/api/v1/analyses", json={"asset_id": asset["id"], "preset": "image"}
    ).json()
    return asset, analysis


def test_vlm_is_disabled_by_default_and_does_not_offer_download(client: TestClient) -> None:
    capability = client.get("/api/v1/capabilities").json()["vlm_localization"]
    assert capability == {
        "enabled": False,
        "available": False,
        "status": "disabled",
        "model_id": None,
        "automatic_download": False,
        "requires_manual_review": True,
        "message": "本地图片模型未启用；可以继续手工框选。",
    }

    asset, analysis = _upload_and_analyze(client, _image_bytes(photo_like=True))
    response = client.post(
        "/api/v1/image-suggestions/vlm",
        json={"asset_id": asset["id"], "analysis_id": analysis["id"]},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VLM_NOT_AVAILABLE"


def test_vlm_suggestions_are_review_only_mask_drafts(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    factory_calls = []

    def factory(received_dir: Path, received_manifest: Path, device: str):
        factory_calls.append((received_dir, received_manifest, device))
        return FakeLocalizer()

    settings = Settings(
        data_dir=tmp_path / "data",
        docx_preview_enabled=False,
        pdf_preview_enabled=False,
        worker_start_method="forkserver",
        vlm_enabled=True,
        vlm_model_dir=model_dir,
        vlm_model_manifest=manifest_path,
        vlm_device="cpu",
    )
    with TestClient(create_app(settings, vlm_localizer_factory=factory)) as client:
        capability = client.get("/api/v1/capabilities").json()["vlm_localization"]
        assert capability["status"] == "ready"
        assert capability["automatic_download"] is False
        assert capability["requires_manual_review"] is True

        asset, analysis = _upload_and_analyze(client, _image_bytes(photo_like=True))
        response = client.post(
            "/api/v1/image-suggestions/vlm",
            json={"asset_id": asset["id"], "analysis_id": analysis["id"]},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "suggested"
        assert result["photo_scene"]["eligible"] is True
        assert result["regions"] == [
            {
                "x0": 5.0,
                "y0": 7.0,
                "x1": 25.0,
                "y1": 18.0,
                "transform_id": analysis["image_metadata"]["transform_id"],
            }
        ]
        assert len(factory_calls) == 1
        assert client.get("/api/v1/tasks").json() == []


def test_photo_gate_rejection_skips_model_loading(tmp_path: Path) -> None:
    model_dir, manifest_path = _model_fixture(tmp_path)
    factory_calls = []

    def factory(model_dir: Path, manifest_path: Path, device: str):
        factory_calls.append((model_dir, manifest_path, device))
        return FakeLocalizer()

    settings = Settings(
        data_dir=tmp_path / "data",
        docx_preview_enabled=False,
        pdf_preview_enabled=False,
        worker_start_method="forkserver",
        vlm_enabled=True,
        vlm_model_dir=model_dir,
        vlm_model_manifest=manifest_path,
    )
    with TestClient(create_app(settings, vlm_localizer_factory=factory)) as client:
        asset, analysis = _upload_and_analyze(client, _image_bytes(photo_like=False))
        result = client.post(
            "/api/v1/image-suggestions/vlm",
            json={"asset_id": asset["id"], "analysis_id": analysis["id"]},
        ).json()

    assert result["status"] == "photo_gate_rejected"
    assert result["regions"] == []
    assert factory_calls == []
