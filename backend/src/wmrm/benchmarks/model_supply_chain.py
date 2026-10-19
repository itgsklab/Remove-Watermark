from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


class ModelSupplyChainError(ValueError):
    """Raised when an evaluation model manifest weakens the local-only policy."""


_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_REQUIRED_POLICY = {
    "approved_use": "offline_evaluation_only",
    "automatic_download": False,
    "bundled_in_release": False,
    "allow_remote_code": False,
    "allow_pickle_weights": False,
    "required_weight_format": "safetensors",
    "require_exact_revision": True,
    "require_sha256_verification": True,
    "product_integration": False,
}


def audit_model_manifest(
    manifest_path: Path,
    *,
    model_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ModelSupplyChainError("Unsupported model manifest schema version.")

    model_id = _required_text(manifest, "model_id")
    revision = _required_text(manifest, "revision")
    if not _REVISION.fullmatch(revision):
        raise ModelSupplyChainError("Model revision must be an exact 40-character commit SHA.")
    if manifest.get("review_status") != "approved_for_evaluation_only":
        raise ModelSupplyChainError("Model is not approved for isolated evaluation.")

    licenses = manifest.get("licenses")
    if not isinstance(licenses, dict):
        raise ModelSupplyChainError("Model manifest must record code and weight licenses.")
    for name in ("code", "weights"):
        license_entry = licenses.get(name)
        if not isinstance(license_entry, dict):
            raise ModelSupplyChainError(f"Missing {name} license record.")
        _required_text(license_entry, "spdx")
        _required_https_url(license_entry, "source")
        digest = _required_text(license_entry, "sha256")
        if not _SHA256.fullmatch(digest):
            raise ModelSupplyChainError(f"Invalid {name} license digest.")

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ModelSupplyChainError("Model manifest must record authoritative sources.")
    _required_https_url(source, "model_repository")
    _required_https_url(source, "code_repository")
    _required_https_url(source, "runtime_documentation")

    policy = manifest.get("runtime_policy")
    if policy != _REQUIRED_POLICY:
        raise ModelSupplyChainError("Model manifest weakens the evaluation-only runtime policy.")

    dependencies = manifest.get("runtime_dependencies")
    if not isinstance(dependencies, list) or not dependencies:
        raise ModelSupplyChainError("Model manifest must pin runtime dependencies.")
    dependency_names: set[str] = set()
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise ModelSupplyChainError("Invalid runtime dependency record.")
        name = _required_text(dependency, "name")
        version = _required_text(dependency, "version")
        if name in dependency_names or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ModelSupplyChainError("Runtime dependencies must have unique package names.")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)+(?:[A-Za-z0-9.-]*)?", version):
            raise ModelSupplyChainError("Runtime dependencies must use exact versions.")
        dependency_names.add(name)

    files = manifest.get("allowed_files")
    if not isinstance(files, list) or not files:
        raise ModelSupplyChainError("Model manifest has no allowed files.")
    seen: set[str] = set()
    total_size = 0
    weight_count = 0
    for entry in files:
        if not isinstance(entry, dict):
            raise ModelSupplyChainError("Invalid allowed-file record.")
        relative = _required_text(entry, "path")
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or relative in seen:
            raise ModelSupplyChainError("Allowed model paths must be unique and contained.")
        if path.suffix not in {".json", ".safetensors"}:
            raise ModelSupplyChainError("Only JSON metadata and Safetensors weights are allowed.")
        size = entry.get("size_bytes")
        digest = entry.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ModelSupplyChainError("Allowed model files require positive byte sizes.")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ModelSupplyChainError("Allowed model files require SHA-256 digests.")
        seen.add(relative)
        total_size += size
        weight_count += path.suffix == ".safetensors"
    if weight_count != 1:
        raise ModelSupplyChainError("Manifest must allow exactly one Safetensors weight file.")

    excluded = manifest.get("explicitly_excluded_files")
    if not isinstance(excluded, list) or not any(
        isinstance(item, dict)
        and str(item.get("path", "")).endswith((".pt", ".pth", ".bin"))
        for item in excluded
    ):
        raise ModelSupplyChainError("Manifest must document excluded executable weight formats.")

    local_verified = False
    if model_dir is not None:
        _verify_local_directory(model_dir, files)
        local_verified = True

    return {
        "schema_version": 1,
        "model_id": model_id,
        "revision": revision,
        "review_status": manifest["review_status"],
        "allowed_file_count": len(files),
        "weight_format": "safetensors",
        "total_size_bytes": total_size,
        "runtime_dependencies": [
            f"{item['name']}=={item['version']}" for item in dependencies
        ],
        "policy_gate": "pass",
        "license_gate": "pass",
        "digest_gate": "pass",
        "local_files_verified": local_verified,
        "evaluation_allowed": True,
        "product_integration_allowed": False,
        "release_claim_allowed": False,
    }


def write_report(report: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    dependencies = ", ".join(f"`{item}`" for item in report["runtime_dependencies"])
    markdown_path.write_text(
        "\n".join(
            [
                "# Segmentation model supply-chain review",
                "",
                f"Model: `{report['model_id']}`",
                f"Revision: `{report['revision']}`",
                f"Review status: **{report['review_status']}**",
                "",
                f"Allowed files: {report['allowed_file_count']}",
                f"Total bytes: {report['total_size_bytes']}",
                f"Weight format: `{report['weight_format']}`",
                f"Runtime dependencies: {dependencies}",
                "",
                f"Policy gate: **{report['policy_gate']}**",
                f"License gate: **{report['license_gate']}**",
                f"Digest gate: **{report['digest_gate']}**",
                f"Local files verified: **{str(report['local_files_verified']).lower()}**",
                "",
                "Evaluation is allowed only after an explicit local download and byte "
                "verification. ",
                "Product integration and release claims remain prohibited.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _verify_local_directory(model_dir: Path, files: list[dict[str, Any]]) -> None:
    root = model_dir.expanduser().resolve()
    expected = {entry["path"] for entry in files}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    if actual != expected:
        raise ModelSupplyChainError("Local model directory differs from the allowlist.")
    for entry in files:
        path = (root / entry["path"]).resolve()
        if root not in path.parents or path.is_symlink():
            raise ModelSupplyChainError("Local model file leaves the reviewed directory.")
        if path.stat().st_size != entry["size_bytes"]:
            raise ModelSupplyChainError(f"Unexpected size for {entry['path']}.")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            raise ModelSupplyChainError(f"Unexpected digest for {entry['path']}.")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelSupplyChainError("Cannot read model manifest.") from exc
    if not isinstance(payload, dict):
        raise ModelSupplyChainError("Model manifest must be a JSON object.")
    return payload


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ModelSupplyChainError(f"Missing model manifest field: {field}")
    return value.strip()


def _required_https_url(payload: dict[str, Any], field: str) -> str:
    value = _required_text(payload, field)
    if not value.startswith("https://"):
        raise ModelSupplyChainError(f"Model manifest URL must use HTTPS: {field}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an evaluation-only model manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    args = parser.parse_args()
    report = audit_model_manifest(args.manifest, model_dir=args.model_dir)
    write_report(report, args.report_json, args.report_md)


if __name__ == "__main__":
    main()
