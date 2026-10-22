from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import tempfile
from functools import partial
from pathlib import Path, PurePosixPath

VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:rc[1-9]\d*)?")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
MAX_MEMBER_BYTES = 2 * 1024**3
MAX_TOTAL_BYTES = 4 * 1024**3


class BundleVerificationError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(name: str, root_name: str) -> PurePosixPath:
    if not name or "\\" in name or "\n" in name or "\r" in name:
        raise BundleVerificationError(f"unsafe archive path: {name!r}")
    stripped = name.removesuffix("/")
    raw_parts = stripped.split("/")
    path = PurePosixPath(stripped)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise BundleVerificationError(f"unsafe archive path: {name!r}")
    if not path.parts or path.parts[0] != root_name:
        raise BundleVerificationError(f"archive member is outside {root_name}: {name!r}")
    if len(path.parts) == 1:
        return PurePosixPath(".")
    return PurePosixPath(*path.parts[1:])


def parse_checksums(payload: bytes) -> dict[PurePosixPath, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BundleVerificationError("SHA256SUMS is not valid UTF-8") from exc
    checksums: dict[PurePosixPath, str] = {}
    for line_number, line in enumerate(text.splitlines(), start=1):
        parts = line.split("  ", maxsplit=1)
        if len(parts) != 2 or not SHA256_PATTERN.fullmatch(parts[0]):
            raise BundleVerificationError(f"invalid SHA256SUMS line {line_number}")
        raw_parts = parts[1].split("/")
        relative = PurePosixPath(parts[1])
        if (
            relative.is_absolute()
            or any(part in {"", ".", ".."} for part in raw_parts)
            or "\\" in parts[1]
            or "\n" in parts[1]
            or "\r" in parts[1]
        ):
            raise BundleVerificationError(f"unsafe SHA256SUMS path on line {line_number}")
        if relative == PurePosixPath("SHA256SUMS"):
            raise BundleVerificationError("SHA256SUMS must not checksum itself")
        if relative in checksums:
            raise BundleVerificationError(f"duplicate SHA256SUMS path: {relative}")
        checksums[relative] = parts[0]
    if not checksums:
        raise BundleVerificationError("SHA256SUMS is empty")
    return checksums


def verify_bundle(
    bundle: Path,
    *,
    version: str,
    expected_sha256: str | None = None,
    source_date_epoch: int | None = None,
) -> dict[str, object]:
    if not VERSION_PATTERN.fullmatch(version):
        raise BundleVerificationError(f"invalid release version: {version!r}")
    if not bundle.is_file() or bundle.is_symlink():
        raise BundleVerificationError(f"bundle must be a regular file: {bundle}")
    if expected_sha256 is not None and not SHA256_PATTERN.fullmatch(expected_sha256):
        raise BundleVerificationError(
            "expected SHA-256 must be 64 lowercase hexadecimal characters"
        )

    archive_sha256 = file_sha256(bundle)
    if expected_sha256 is not None and archive_sha256 != expected_sha256:
        raise BundleVerificationError(
            f"bundle SHA-256 mismatch: expected {expected_sha256}, got {archive_sha256}"
        )

    root_name = f"remove-watermark-web-{version}"
    members_by_path: dict[PurePosixPath, tarfile.TarInfo] = {}
    file_hashes: dict[PurePosixPath, str] = {}
    total_bytes = 0
    timestamps: set[int] = set()
    try:
        with tarfile.open(bundle, mode="r:gz") as archive:
            for member in archive.getmembers():
                relative = safe_relative_path(member.name, root_name)
                if relative in members_by_path:
                    raise BundleVerificationError(f"duplicate archive path: {member.name}")
                members_by_path[relative] = member
                if not (member.isdir() or member.isfile()):
                    raise BundleVerificationError(
                        f"unsupported archive member type: {member.name}"
                    )
                expected_mode = 0o755 if member.isdir() else 0o644
                if member.mode & 0o7777 != expected_mode:
                    raise BundleVerificationError(f"unexpected mode for {member.name}")
                if member.uid != 0 or member.gid != 0:
                    raise BundleVerificationError(f"unexpected ownership for {member.name}")
                if member.uname != "root" or member.gname != "root":
                    raise BundleVerificationError(f"unexpected owner names for {member.name}")
                timestamps.add(member.mtime)
                if member.mtime < 0:
                    raise BundleVerificationError(f"negative timestamp for {member.name}")
                if source_date_epoch is not None and member.mtime != source_date_epoch:
                    raise BundleVerificationError(f"unexpected timestamp for {member.name}")
                if not member.isfile():
                    continue
                if member.size > MAX_MEMBER_BYTES:
                    raise BundleVerificationError(f"archive member is too large: {member.name}")
                total_bytes += member.size
                if total_bytes > MAX_TOTAL_BYTES:
                    raise BundleVerificationError("archive expands beyond the verification limit")
                stream = archive.extractfile(member)
                if stream is None:
                    raise BundleVerificationError(f"cannot read archive member: {member.name}")
                digest = hashlib.sha256()
                for chunk in iter(partial(stream.read, 1024 * 1024), b""):
                    digest.update(chunk)
                file_hashes[relative] = digest.hexdigest()

            if PurePosixPath(".") not in members_by_path:
                raise BundleVerificationError("archive root directory is missing")
            if not members_by_path[PurePosixPath(".")].isdir():
                raise BundleVerificationError("archive root is not a directory")
            for relative in members_by_path:
                if relative == PurePosixPath("."):
                    continue
                for parent in relative.parents:
                    if parent == PurePosixPath("."):
                        break
                    parent_member = members_by_path.get(parent)
                    if parent_member is None or not parent_member.isdir():
                        raise BundleVerificationError(
                            f"archive parent directory is missing: {parent}"
                        )
            if len(timestamps) != 1:
                raise BundleVerificationError(
                    "archive members do not share one normalized timestamp"
                )

            required = {
                PurePosixPath("LICENSE"),
                PurePosixPath("README.md"),
                PurePosixPath("SHA256SUMS"),
                PurePosixPath("frontend/index.html"),
                PurePosixPath("packages") / f"wmrm-{version}-py3-none-any.whl",
                PurePosixPath("packages") / f"wmrm-{version}.tar.gz",
            }
            missing = sorted(str(path) for path in required - file_hashes.keys())
            if missing:
                raise BundleVerificationError(
                    f"required bundle files are missing: {', '.join(missing)}"
                )
            if not any(
                path.parts[:2] == ("frontend", "assets") and len(path.parts) > 2
                for path in file_hashes
            ):
                raise BundleVerificationError("compiled frontend assets are missing")

            checksum_member = members_by_path[PurePosixPath("SHA256SUMS")]
            checksum_stream = archive.extractfile(checksum_member)
            if checksum_stream is None:
                raise BundleVerificationError("cannot read SHA256SUMS")
            expected_files = parse_checksums(checksum_stream.read())
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BundleVerificationError(f"cannot read Web bundle: {exc}") from exc

    actual_files = {
        path: digest
        for path, digest in file_hashes.items()
        if path.name != "SHA256SUMS"
    }
    if expected_files.keys() != actual_files.keys():
        missing = sorted(str(path) for path in actual_files.keys() - expected_files.keys())
        extra = sorted(str(path) for path in expected_files.keys() - actual_files.keys())
        details = []
        if missing:
            details.append(f"unlisted files: {', '.join(missing)}")
        if extra:
            details.append(f"missing files: {', '.join(extra)}")
        raise BundleVerificationError("SHA256SUMS file set mismatch: " + "; ".join(details))
    mismatches = sorted(
        str(path) for path in actual_files if actual_files[path] != expected_files[path]
    )
    if mismatches:
        raise BundleVerificationError(f"SHA-256 mismatch for: {', '.join(mismatches)}")

    timestamp = next(iter(timestamps))
    return {
        "schema_version": 1,
        "verified": True,
        "bundle": bundle.name,
        "version": version,
        "sha256": archive_sha256,
        "size_bytes": bundle.stat().st_size,
        "source_date_epoch": timestamp,
        "payload_file_count": len(actual_files),
        "payload_size_bytes": sum(
            member.size for path, member in members_by_path.items() if path in actual_files
        ),
    }


def extract_verified_bundle(bundle: Path, destination: Path, *, version: str) -> Path:
    if destination.exists():
        raise BundleVerificationError(f"extraction destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    root_name = f"remove-watermark-web-{version}"
    try:
        with tarfile.open(bundle, mode="r:gz") as archive:
            for member in archive.getmembers():
                relative = safe_relative_path(member.name, root_name)
                target = temporary / root_name
                if relative != PurePosixPath("."):
                    target = target.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=False)
                    target.chmod(0o755)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise BundleVerificationError(f"cannot extract archive member: {member.name}")
                with target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
                target.chmod(0o644)
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination / root_name


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and safely extract a Web release bundle.")
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--source-date-epoch", type=int)
    parser.add_argument("--extract-to", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        report = verify_bundle(
            args.bundle.resolve(),
            version=args.version,
            expected_sha256=args.expected_sha256,
            source_date_epoch=args.source_date_epoch,
        )
        if args.extract_to is not None:
            root = extract_verified_bundle(
                args.bundle.resolve(), args.extract_to.resolve(), version=args.version
            )
            report["extracted_root"] = root.name
        if args.report_json is not None:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    except BundleVerificationError as exc:
        parser.exit(1, f"web bundle rejected: {exc}\n")
    print(
        f"web bundle verified: {report['bundle']} "
        f"({report['payload_file_count']} payload files, sha256={report['sha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
