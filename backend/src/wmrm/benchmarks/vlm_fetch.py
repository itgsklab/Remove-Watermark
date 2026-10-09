from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from wmrm.adapters.images.florence2 import verify_model_directory


def fetch_pinned_model(manifest_path: Path, destination: Path) -> Path:
    """Explicitly download only reviewed model files and verify every byte."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    model_id = _required_text(manifest, "model_id")
    revision = _required_text(manifest, "revision")
    files = manifest.get("allowed_files")
    if not isinstance(files, list) or not files:
        raise ValueError("The model manifest has no allowed files.")
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    for record in files:
        if not isinstance(record, dict):
            raise ValueError("Invalid model file record.")
        relative = _required_text(record, "path")
        expected_size = record.get("size_bytes")
        expected_sha = _required_text(record, "sha256")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError("Model file path leaves the destination.")
        if not isinstance(expected_size, int) or expected_size < 0:
            raise ValueError("Invalid model file size.")
        target = destination / relative
        if (
            target.is_file()
            and not target.is_symlink()
            and target.stat().st_size == expected_size
            and _sha256(target) == expected_sha
        ):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.partial")
        url = f"https://huggingface.co/{model_id}/resolve/{revision}/{relative}"
        request = urllib.request.Request(url, headers={"User-Agent": "wmrm-model-fetch/1"})
        digest = hashlib.sha256()
        downloaded = 0
        try:
            with (
                urllib.request.urlopen(request, timeout=60) as response,
                temporary.open("wb") as out,
            ):
                final_url = response.geturl()
                final = urlsplit(final_url)
                if final.scheme != "https" or not (
                    final.hostname == "huggingface.co"
                    or (final.hostname or "").endswith(".hf.co")
                ):
                    raise ValueError("Model download redirected to an unapproved host.")
                while chunk := response.read(1024 * 1024):
                    downloaded += len(chunk)
                    if downloaded > expected_size:
                        raise ValueError(f"Downloaded model file is too large: {relative}")
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if downloaded != expected_size or digest.hexdigest() != expected_sha:
                raise ValueError(f"Downloaded model file failed verification: {relative}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    verify_model_directory(destination, manifest_path)
    return destination


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing model manifest field: {field}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch the reviewed Florence-2 model files.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    output = fetch_pinned_model(args.manifest, args.destination)
    print(f"Verified local model: {output}")


if __name__ == "__main__":
    main()
