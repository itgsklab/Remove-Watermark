from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


class SmokeError(RuntimeError):
    pass


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def installed_web_command() -> Path:
    name = "wmrm-web.exe" if os.name == "nt" else "wmrm-web"
    # Keep the virtual-environment path; resolving its Python symlink would jump to the
    # base interpreter and hide console scripts installed beside it.
    command = Path(sys.executable).absolute().parent / name
    if not command.is_file():
        raise SmokeError(f"installed wmrm-web command was not found beside {sys.executable}")
    return command


def read_url(url: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(url, timeout=2) as response:
        return response.status, response.read()


def smoke_bundle(bundle_root: Path, *, version: str, timeout_seconds: float) -> dict[str, object]:
    frontend = bundle_root / "frontend"
    if not (frontend / "index.html").is_file() or not (frontend / "assets").is_dir():
        raise SmokeError(f"extracted frontend is incomplete: {frontend}")
    if timeout_seconds <= 0:
        raise SmokeError("timeout must be positive")

    port = available_port()
    environment = os.environ.copy()
    for name in tuple(environment):
        if name.startswith("WMRM_") or name == "PYTHONPATH":
            environment.pop(name, None)

    with tempfile.TemporaryDirectory(prefix="wmrm-web-smoke-") as data_dir:
        command = [
            str(installed_web_command()),
            "--frontend-dir",
            str(frontend.resolve()),
            "--data-dir",
            data_dir,
            "--port",
            str(port),
        ]
        process = subprocess.Popen(
            command,
            cwd=bundle_root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + timeout_seconds
        last_error = "service did not answer"
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    output = process.stdout.read() if process.stdout is not None else ""
                    raise SmokeError(
                        f"wmrm-web exited with code {process.returncode}: {output.strip()}"
                    )
                try:
                    health_status, health_body = read_url(
                        f"http://127.0.0.1:{port}/api/v1/health"
                    )
                    index_status, index_body = read_url(f"http://127.0.0.1:{port}/")
                    health = json.loads(health_body)
                    if health_status != 200 or health.get("version") != version:
                        raise SmokeError("health endpoint returned the wrong version")
                    if index_status != 200 or b'<div id="app"></div>' not in index_body:
                        raise SmokeError("compiled Vue entry page was not served")
                    return {
                        "schema_version": 1,
                        "verified": True,
                        "version": version,
                        "health_status": health_status,
                        "frontend_status": index_status,
                    }
                except (OSError, urllib.error.URLError, json.JSONDecodeError, SmokeError) as exc:
                    last_error = str(exc)
                    time.sleep(0.1)
            raise SmokeError(f"wmrm-web did not become ready: {last_error}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start an installed wmrm-web command against an extracted release bundle."
    )
    parser.add_argument("--bundle-root", required=True, type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=20)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    try:
        report = smoke_bundle(
            args.bundle_root.resolve(),
            version=args.version,
            timeout_seconds=args.timeout_seconds,
        )
        if args.report_json is not None:
            args.report_json.parent.mkdir(parents=True, exist_ok=True)
            args.report_json.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    except SmokeError as exc:
        parser.exit(1, f"Web bundle smoke check failed: {exc}\n")
    print(f"extracted Web bundle started successfully: wmrm {report['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
