from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend"
BUILD = ROOT / "packaging" / "build"
DIST = ROOT / "dist"
SPEC = ROOT / "packaging" / "watermark_remover.spec"


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def build_timestamp() -> str:
    if epoch := os.environ.get("SOURCE_DATE_EPOCH"):
        value = int(epoch)
    else:
        value = int(git_value("show", "-s", "--format=%ct", "HEAD"))
    return datetime.fromtimestamp(value, UTC).isoformat()


def stage_frontend(skip_npm_ci: bool) -> None:
    if not skip_npm_ci:
        run(["npm", "ci"], cwd=FRONTEND)
    run(["npm", "run", "build"], cwd=FRONTEND)
    target = BUILD / "frontend-dist"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(FRONTEND / "dist", target)


def write_build_info() -> None:
    BUILD.mkdir(parents=True, exist_ok=True)
    payload = {
        "app_version": "0.1.0.dev0",
        "built_at": build_timestamp(),
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_dirty": bool(git_value("status", "--porcelain")),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "inputs": {
            "backend_pyproject_sha256": sha256(BACKEND / "pyproject.toml"),
            "frontend_lock_sha256": sha256(FRONTEND / "package-lock.json"),
            "packaging_constraints_sha256": sha256(ROOT / "packaging" / "constraints.txt"),
        },
    }
    (BUILD / "build-info.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def output_path() -> Path:
    if platform.system() == "Darwin":
        return DIST / "Watermark Remover.app"
    suffix = ".exe" if platform.system() == "Windows" else ""
    return DIST / "Watermark Remover" / f"Watermark Remover{suffix}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the platform-native desktop preview.")
    parser.add_argument(
        "--skip-npm-ci",
        action="store_true",
        help="Use the existing node_modules directory instead of running npm ci.",
    )
    args = parser.parse_args()
    stage_frontend(args.skip_npm_ci)
    write_build_info()
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "--distpath",
            str(DIST),
            "--workpath",
            str(BUILD / "pyinstaller"),
            str(SPEC),
        ]
    )
    output = output_path()
    if not output.exists():
        raise SystemExit(f"Desktop output was not created: {output}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
