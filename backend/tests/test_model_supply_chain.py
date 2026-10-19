from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from wmrm.benchmarks.model_supply_chain import ModelSupplyChainError, audit_model_manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "models" / "sam2-hiera-tiny.json"


def test_sam2_manifest_passes_evaluation_only_supply_chain_gate() -> None:
    report = audit_model_manifest(MANIFEST)

    assert report["model_id"] == "facebook/sam2-hiera-tiny"
    assert report["allowed_file_count"] == 5
    assert report["weight_format"] == "safetensors"
    assert report["evaluation_allowed"] is True
    assert report["product_integration_allowed"] is False
    assert report["release_claim_allowed"] is False
    assert report["local_files_verified"] is False


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
