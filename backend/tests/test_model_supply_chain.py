from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from wmrm.benchmarks.model_supply_chain import ModelSupplyChainError, audit_model_manifest
from wmrm.benchmarks.vlm_fetch import fetch_pinned_model

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "models" / "sam2-hiera-tiny.json"
SEGMENTATION_REQUIREMENTS = ROOT / "backend" / "requirements-segmentation-eval.txt"


def test_sam2_manifest_passes_evaluation_only_supply_chain_gate() -> None:
    report = audit_model_manifest(MANIFEST)

    assert report["model_id"] == "facebook/sam2-hiera-tiny"
    assert report["allowed_file_count"] == 5
    assert report["weight_format"] == "safetensors"
    assert report["evaluation_allowed"] is True
    assert report["product_integration_allowed"] is False
    assert report["release_claim_allowed"] is False
    assert report["local_files_verified"] is False


def test_segmentation_environment_pins_every_manifest_dependency() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    locked = {
        line.strip().lower()
        for line in SEGMENTATION_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    expected = {
        f"{item['name']}=={item['version']}".lower()
        for item in payload["runtime_dependencies"]
    }
    assert expected <= locked


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (("runtime_policy", "automatic_download", True), "runtime policy"),
        (("runtime_policy", "allow_remote_code", True), "runtime policy"),
        (("runtime_policy", "allow_pickle_weights", True), "runtime policy"),
        (("allowed_files", 0, "model.pt"), "JSON metadata and Safetensors"),
    ],
)
def test_manifest_rejects_weakened_policy(
    tmp_path: Path, mutation: tuple[str, str | int, object], message: str
) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    section, field, value = mutation
    if section == "allowed_files":
        payload[section][field]["path"] = value
    else:
        payload[section][field] = value
    candidate = tmp_path / "manifest.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelSupplyChainError, match=message):
        audit_model_manifest(candidate)


def test_local_directory_verifies_exact_allowlist_and_digests(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    for index, entry in enumerate(payload["allowed_files"]):
        data = f"fixture-{index}".encode()
        entry["size_bytes"] = len(data)
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        (model_dir / entry["path"]).write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    report = audit_model_manifest(manifest, model_dir=model_dir)
    assert report["local_files_verified"] is True

    (model_dir / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ModelSupplyChainError, match="allowlist"):
        audit_model_manifest(manifest, model_dir=model_dir)


def test_explicit_fetch_dispatches_to_evaluation_manifest_audit(
    tmp_path: Path, monkeypatch
) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    file_payloads = {
        "model.safetensors": b"safe-weight-fixture",
        "config.json": b"{}",
    }
    payload["allowed_files"] = [
        {
            "path": name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        for name, data in file_payloads.items()
    ]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    class Response(io.BytesIO):
        def geturl(self) -> str:
            return "https://cdn-lfs.hf.co/verified"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_open(request, timeout):
        assert timeout == 60
        return Response(file_payloads[Path(request.full_url).name])

    monkeypatch.setattr("urllib.request.urlopen", fake_open)
    destination = tmp_path / "model"

    assert fetch_pinned_model(manifest, destination) == destination.resolve()
    assert audit_model_manifest(manifest, model_dir=destination)["local_files_verified"] is True
