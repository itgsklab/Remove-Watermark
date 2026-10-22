from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:rc[1-9]\d*)?")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
CHECKSUM_LINE_PATTERN = re.compile(r"([0-9a-f]{64})  ([^\r\n]+)")

MAX_ARCHIVE_DEPTH = 3
MAX_ARCHIVE_MEMBERS = 20_000
MAX_MEMBER_BYTES = 512 * 1024**2
MAX_TOTAL_BYTES = 2 * 1024**3

FORBIDDEN_COMPONENTS = {
    ".git",
    ".pytest_cache",
    ".wmrm-data",
    "__pycache__",
    "node_modules",
    "private-fixtures",
    "work",
}
FORBIDDEN_BASENAMES = {
    ".coverage",
    ".ds_store",
    ".env",
    ".env.local",
    "plan.md",
    "project_expansion_plan.md",
    "prompts.md",
    "status.md",
}
MODEL_WEIGHT_SUFFIXES = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
}

CONTENT_PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"(?:gh[opusr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{40,255})"),
    "openai-token": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{32,}"),
    "slack-token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "aws-access-key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "macos-home-path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    "linux-home-path": re.compile(rb"/home/[A-Za-z0-9._-]+/"),
    "windows-home-path": re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+\\"),
}


class AssetAuditError(RuntimeError):
    pass


@dataclass
class AuditState:
    archive_count: int = 0
    archive_member_count: int = 0
    file_count: int = 0
    scanned_bytes: int = 0


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_regular_file(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise AssetAuditError(f"{label} must be a regular file: {path.name}")
    if path.stat().st_size > MAX_MEMBER_BYTES:
        raise AssetAuditError(f"{label} exceeds the per-file audit limit: {path.name}")
    return path.read_bytes()


def expected_asset_names(version: str) -> set[str]:
    return {
        "SHA256SUMS",
        "release-manifest.json",
        f"remove-watermark-web-{version}.tar.gz",
        f"wmrm-{version}-py3-none-any.whl",
        f"wmrm-{version}.tar.gz",
    }


def validate_member_path(name: str, context: str) -> PurePosixPath:
    if not name or "\\" in name or "\r" in name or "\n" in name:
        raise AssetAuditError("unsafe path detected in release archive")
    stripped = name.removesuffix("/")
    raw_parts = stripped.split("/")
    path = PurePosixPath(stripped)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise AssetAuditError("unsafe path detected in release archive")
    lowered = tuple(part.casefold() for part in raw_parts)
    if any(part in FORBIDDEN_COMPONENTS for part in lowered):
        raise AssetAuditError("private build path detected in release archive")
    if lowered[-1] in FORBIDDEN_BASENAMES or lowered[-1].startswith(".env."):
        raise AssetAuditError("private file detected in release archive")
    if path.suffix.casefold() in MODEL_WEIGHT_SUFFIXES:
        raise AssetAuditError("model weight is forbidden in release assets")
    return path


def audit_content(payload: bytes, context: str, state: AuditState) -> None:
    state.file_count += 1
    state.scanned_bytes += len(payload)
    if state.file_count > MAX_ARCHIVE_MEMBERS:
        raise AssetAuditError("release assets contain too many files")
    if state.scanned_bytes > MAX_TOTAL_BYTES:
        raise AssetAuditError("release assets exceed the expanded audit limit")
    for label, pattern in CONTENT_PATTERNS.items():
        if pattern.search(payload):
            raise AssetAuditError(f"{label} detected in release content")


def is_archive(name: str) -> bool:
    lowered = name.casefold()
    return lowered.endswith((".whl", ".zip", ".tar.gz", ".tgz", ".tar"))


def audit_zip(payload: bytes, context: str, depth: int, state: AuditState) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if len(archive.infolist()) > MAX_ARCHIVE_MEMBERS - state.archive_member_count:
                raise AssetAuditError("release assets contain too many archive members")
            seen: set[PurePosixPath] = set()
            for info in archive.infolist():
                state.archive_member_count += 1
                path = validate_member_path(info.filename, context)
                if path in seen:
                    raise AssetAuditError("duplicate path detected in release archive")
                seen.add(path)
                unix_mode = info.external_attr >> 16
                file_type = unix_mode & 0o170000
                if file_type not in {0, 0o040000, 0o100000}:
                    raise AssetAuditError("link or special file detected in release archive")
                if info.is_dir():
                    continue
                if info.file_size > MAX_MEMBER_BYTES:
                    raise AssetAuditError("oversized release archive member")
                child = archive.read(info)
                audit_payload(child, f"{context}!/{path}", str(path), depth + 1, state)
    except AssetAuditError:
        raise
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise AssetAuditError("invalid ZIP archive in release assets") from exc


def audit_tar(payload: bytes, context: str, depth: int, state: AuditState) -> None:
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
            seen: set[PurePosixPath] = set()
            for member in archive:
                state.archive_member_count += 1
                if state.archive_member_count > MAX_ARCHIVE_MEMBERS:
                    raise AssetAuditError("release assets contain too many archive members")
                path = validate_member_path(member.name, context)
                if path in seen:
                    raise AssetAuditError("duplicate path detected in release archive")
                seen.add(path)
                if not (member.isdir() or member.isfile()):
                    raise AssetAuditError("link or special file detected in release archive")
                if member.isdir():
                    continue
                if member.size > MAX_MEMBER_BYTES:
                    raise AssetAuditError("oversized release archive member")
                stream = archive.extractfile(member)
                if stream is None:
                    raise AssetAuditError("unreadable release archive member")
                child = stream.read(MAX_MEMBER_BYTES + 1)
                if len(child) > MAX_MEMBER_BYTES:
                    raise AssetAuditError("oversized release archive member")
                audit_payload(child, f"{context}!/{path}", str(path), depth + 1, state)
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise AssetAuditError("invalid tar archive in release assets") from exc


def audit_payload(
    payload: bytes,
    context: str,
    name: str,
    depth: int,
    state: AuditState,
) -> None:
    validate_member_path(name, context)
    audit_content(payload, context, state)
    if not is_archive(name):
        return
    if depth > MAX_ARCHIVE_DEPTH:
        raise AssetAuditError("nested archive depth exceeded in release assets")
    state.archive_count += 1
    if name.casefold().endswith((".whl", ".zip")):
        audit_zip(payload, context, depth, state)
    else:
        audit_tar(payload, context, depth, state)


def parse_checksums(payload: bytes) -> dict[str, str]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise AssetAuditError("SHA256SUMS is not UTF-8") from exc
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        match = CHECKSUM_LINE_PATTERN.fullmatch(line)
        if match is None:
            raise AssetAuditError(f"invalid SHA256SUMS line {line_number}")
        digest, name = match.groups()
        validate_member_path(name, "SHA256SUMS")
        if "/" in name or name in checksums:
            raise AssetAuditError(f"invalid or duplicate SHA256SUMS asset: {name}")
        checksums[name] = digest
    return checksums


def load_manifest(payload: bytes, *, version: str) -> dict[str, object]:
    try:
        manifest = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssetAuditError(f"release-manifest.json is invalid: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise AssetAuditError("release manifest must be a schema v1 object")
    if manifest.get("version") != version:
        raise AssetAuditError("release manifest version does not match the audit version")
    return manifest


def manifest_artifacts(manifest: dict[str, object]) -> dict[str, tuple[int, str]]:
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise AssetAuditError("release manifest artifacts must be a list")
    artifacts: dict[str, tuple[int, str]] = {}
    for index, raw in enumerate(raw_artifacts):
        if not isinstance(raw, dict) or set(raw) != {"name", "bytes", "sha256"}:
            raise AssetAuditError(f"invalid release manifest artifact at index {index}")
        name, size, digest = raw["name"], raw["bytes"], raw["sha256"]
        if (
            not isinstance(name, str)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
            or not isinstance(digest, str)
            or not SHA256_PATTERN.fullmatch(digest)
            or name in artifacts
        ):
            raise AssetAuditError(f"invalid release manifest artifact at index {index}")
        validate_member_path(name, "release manifest")
        if "/" in name:
            raise AssetAuditError(f"release manifest artifact must be top-level: {name}")
        artifacts[name] = (size, digest)
    return artifacts


def policy_assets(policy_path: Path, tag: str) -> dict[str, str]:
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetAuditError(f"cannot read release policy: {exc}") from exc
    candidates = policy.get("required_release_candidates") if isinstance(policy, dict) else None
    if not isinstance(candidates, list):
        raise AssetAuditError("release policy has no candidate list")
    for raw in candidates:
        if isinstance(raw, dict) and raw.get("tag") == tag:
            assets = raw.get("assets")
            if not isinstance(assets, dict) or not all(
                isinstance(name, str)
                and isinstance(digest, str)
                and SHA256_PATTERN.fullmatch(digest)
                for name, digest in assets.items()
            ):
                raise AssetAuditError(f"release policy assets are invalid for {tag}")
            return assets
    raise AssetAuditError(f"release policy does not pin {tag}")


def audit_release_assets(
    assets_dir: Path,
    *,
    version: str,
    expected_commit: str | None = None,
    expected_policy_assets: dict[str, str] | None = None,
) -> dict[str, object]:
    if not VERSION_PATTERN.fullmatch(version):
        raise AssetAuditError(f"invalid release version: {version!r}")
    if expected_commit is not None and not COMMIT_PATTERN.fullmatch(expected_commit):
        raise AssetAuditError("expected commit must be a full lowercase Git SHA")
    if not assets_dir.is_dir() or assets_dir.is_symlink():
        raise AssetAuditError("release asset directory is missing or is a symbolic link")

    expected_names = expected_asset_names(version)
    entries = list(assets_dir.iterdir())
    actual_names = {entry.name for entry in entries}
    if actual_names != expected_names or len(entries) != len(expected_names):
        missing = sorted(expected_names - actual_names)
        extra = sorted(actual_names - expected_names)
        raise AssetAuditError(
            f"release asset set mismatch; missing={missing or 'none'}, extra={extra or 'none'}"
        )

    total_asset_bytes = sum(entry.stat().st_size for entry in entries if entry.is_file())
    if total_asset_bytes > MAX_TOTAL_BYTES:
        raise AssetAuditError("release assets exceed the compressed audit limit")
    payloads = {
        name: read_regular_file(assets_dir / name, "release asset")
        for name in expected_names
    }
    digests = {name: sha256_bytes(payload) for name, payload in payloads.items()}
    if expected_policy_assets is not None:
        if expected_policy_assets.keys() != digests.keys():
            raise AssetAuditError("release policy asset set does not match downloaded assets")
        mismatches = sorted(
            name for name in digests if digests[name] != expected_policy_assets[name]
        )
        if mismatches:
            raise AssetAuditError(f"release policy digest mismatch: {', '.join(mismatches)}")

    artifact_names = expected_names - {"SHA256SUMS", "release-manifest.json"}
    checksums = parse_checksums(payloads["SHA256SUMS"])
    if checksums.keys() != artifact_names:
        raise AssetAuditError("SHA256SUMS must list exactly the three distributable artifacts")
    checksum_mismatches = sorted(name for name in artifact_names if checksums[name] != digests[name])
    if checksum_mismatches:
        raise AssetAuditError(f"SHA256SUMS mismatch: {', '.join(checksum_mismatches)}")

    manifest = load_manifest(payloads["release-manifest.json"], version=version)
    manifest_entries = manifest_artifacts(manifest)
    if manifest_entries.keys() != artifact_names:
        raise AssetAuditError("release manifest must list exactly the three distributable artifacts")
    for name in artifact_names:
        if manifest_entries[name] != (len(payloads[name]), digests[name]):
            raise AssetAuditError(f"release manifest metadata mismatch: {name}")
    source = manifest.get("source")
    manifest_commit = source.get("commit") if isinstance(source, dict) else None
    if not isinstance(manifest_commit, str) or not COMMIT_PATTERN.fullmatch(manifest_commit):
        raise AssetAuditError("release manifest source commit is invalid")
    if expected_commit is not None and manifest_commit != expected_commit:
        raise AssetAuditError("release manifest source commit does not match the expected commit")

    state = AuditState()
    for name in sorted(expected_names):
        audit_payload(payloads[name], name, name, 0, state)
    return {
        "schema_version": 1,
        "status": "passed",
        "version": version,
        "source_commit": manifest_commit,
        "asset_count": len(expected_names),
        "archive_count": state.archive_count,
        "archive_member_count": state.archive_member_count,
        "scanned_file_count": state.file_count,
        "scanned_bytes": state.scanned_bytes,
        "assets": [
            {"name": name, "bytes": len(payloads[name]), "sha256": digests[name]}
            for name in sorted(expected_names)
        ],
        "checks": {
            "asset_set": True,
            "checksums": True,
            "manifest": True,
            "archive_paths": True,
            "private_files": True,
            "local_paths": True,
            "credential_patterns": True,
            "model_weights": True,
        },
    }


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a complete Web release asset set.")
    parser.add_argument("--assets-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-commit")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    if (args.policy is None) != (args.tag is None):
        parser.error("--policy and --tag must be supplied together")
    try:
        pinned = policy_assets(args.policy.resolve(), args.tag) if args.policy else None
        report = audit_release_assets(
            args.assets_dir.resolve(),
            version=args.version,
            expected_commit=args.expected_commit,
            expected_policy_assets=pinned,
        )
        if args.report_json:
            write_json(args.report_json.resolve(), report)
    except AssetAuditError as exc:
        parser.exit(1, f"release asset audit failed: {exc}\n")
    print(
        f"release asset audit passed: {report['asset_count']} assets, "
        f"{report['scanned_file_count']} files, {report['archive_count']} archives"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
