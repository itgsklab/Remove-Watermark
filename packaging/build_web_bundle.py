from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import re
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:rc[1-9]\d*)?")


class BundleError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_file(path: Path, label: str) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise BundleError(f"{label} must be a regular file: {path}")
    return path.read_bytes()


def collect_frontend(frontend_dir: Path) -> dict[PurePosixPath, bytes]:
    root = frontend_dir.resolve()
    if not (root / "index.html").is_file() or not (root / "assets").is_dir():
        raise BundleError(f"Incomplete Vue production build: {root}")
    files: dict[PurePosixPath, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BundleError(f"Frontend build contains a symbolic link: {path}")
        if not path.is_file():
            continue
        relative = PurePosixPath(path.relative_to(root).as_posix())
        if any(part in {"", ".", ".."} for part in relative.parts):
            raise BundleError(f"Unsafe frontend path: {relative}")
        if any("\n" in part or "\r" in part for part in relative.parts):
            raise BundleError(f"Frontend path contains a newline: {relative}")
        files[PurePosixPath("frontend") / relative] = path.read_bytes()
    return files


def bundle_readme(version: str, wheel_name: str) -> bytes:
    return f"""# Remove Watermark Web {version}

This bundle contains the compiled Vue interface and the audited Python release artifacts.

Requirements: Python 3.12 or newer and a local network connection for installing Python runtime
dependencies from the configured package index.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install packages/{wheel_name}
.venv/bin/wmrm-web --frontend-dir frontend
```

On Windows, replace `.venv/bin` with `.venv\\Scripts`. Open http://127.0.0.1:8765/ and stop the
service with Ctrl+C in the launching terminal. The service accepts only the loopback host by default.
Process only files you are authorized to modify.
""".encode()


def bundle_payloads(
    *,
    version: str,
    wheel: Path,
    sdist: Path,
    frontend_dir: Path,
    license_path: Path,
) -> dict[PurePosixPath, bytes]:
    if not VERSION_PATTERN.fullmatch(version):
        raise BundleError(f"Invalid release version: {version!r}")
    expected_wheel = f"wmrm-{version}-py3-none-any.whl"
    expected_sdist = f"wmrm-{version}.tar.gz"
    if wheel.name != expected_wheel:
        raise BundleError(f"Unexpected wheel filename: {wheel.name}")
    if sdist.name != expected_sdist:
        raise BundleError(f"Unexpected source-distribution filename: {sdist.name}")

    payloads = collect_frontend(frontend_dir)
    payloads[PurePosixPath("LICENSE")] = read_file(license_path, "License")
    payloads[PurePosixPath("packages") / wheel.name] = read_file(wheel, "Wheel")
    payloads[PurePosixPath("packages") / sdist.name] = read_file(sdist, "Source distribution")
    payloads[PurePosixPath("README.md")] = bundle_readme(version, wheel.name)
    checksums = "".join(
        f"{sha256_bytes(payloads[path])}  {path}\n" for path in sorted(payloads)
    )
    payloads[PurePosixPath("SHA256SUMS")] = checksums.encode()
    return payloads


def add_directory(archive: tarfile.TarFile, name: str, source_date_epoch: int) -> None:
    info = tarfile.TarInfo(name.rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.mtime = source_date_epoch
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info)


def add_file(
    archive: tarfile.TarFile,
    name: str,
    payload: bytes,
    source_date_epoch: int,
) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = source_date_epoch
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    archive.addfile(info, io.BytesIO(payload))


def write_bundle(
    output: Path,
    *,
    version: str,
    payloads: dict[PurePosixPath, bytes],
    source_date_epoch: int,
) -> None:
    if source_date_epoch < 0:
        raise BundleError("SOURCE_DATE_EPOCH must be non-negative.")
    output.parent.mkdir(parents=True, exist_ok=True)
    root_name = f"remove-watermark-web-{version}"
    directories = {PurePosixPath(root_name)}
    for relative in payloads:
        current = PurePosixPath(root_name) / relative
        directories.update(current.parents)
    directories.discard(PurePosixPath("."))

    temporary = output.with_name(f".{output.name}.tmp")
    try:
        with (
            temporary.open("wb") as raw,
            gzip.GzipFile(
                filename="", mode="wb", fileobj=raw, mtime=source_date_epoch
            ) as zipped,
            tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as archive,
        ):
            for directory in sorted(directories, key=lambda item: (len(item.parts), str(item))):
                add_directory(archive, str(directory), source_date_epoch)
            for relative, payload in sorted(payloads.items()):
                add_file(
                    archive,
                    str(PurePosixPath(root_name) / relative),
                    payload,
                    source_date_epoch,
                )
        temporary.replace(output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a reproducible Vue/FastAPI Web release bundle.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--sdist", required=True, type=Path)
    parser.add_argument("--frontend-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-date-epoch", required=True, type=int)
    args = parser.parse_args()
    try:
        payloads = bundle_payloads(
            version=args.version,
            wheel=args.wheel.resolve(),
            sdist=args.sdist.resolve(),
            frontend_dir=args.frontend_dir.resolve(),
            license_path=ROOT / "LICENSE",
        )
        write_bundle(
            args.output.resolve(),
            version=args.version,
            payloads=payloads,
            source_date_epoch=args.source_date_epoch,
        )
    except BundleError as exc:
        parser.exit(1, f"web bundle rejected: {exc}\n")
    print(f"web bundle built: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
