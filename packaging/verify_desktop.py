from __future__ import annotations

import json
import platform
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def executable_path() -> Path:
    if platform.system() == "Darwin":
        return DIST / "Watermark Remover.app" / "Contents" / "MacOS" / "Watermark Remover"
    suffix = ".exe" if platform.system() == "Windows" else ""
    return DIST / "Watermark Remover" / f"Watermark Remover{suffix}"


def available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=1) as response:
        return json.load(response)


def wait_for_health(base_url: str, process: subprocess.Popen[bytes]) -> dict[str, object]:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Desktop process exited early with code {process.returncode}.")
        try:
            return request_json(f"{base_url}/api/v1/health")
        except OSError:
            time.sleep(0.1)
    raise TimeoutError("Desktop health endpoint did not become ready.")


def request_shutdown(base_url: str) -> None:
    request = urllib.request.Request(
        f"{base_url}/api/v1/system/shutdown",
        data=b"{}",
        headers={"Content-Type": "application/json", "Origin": base_url},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        if response.status != 202:
            raise RuntimeError(f"Unexpected shutdown status: {response.status}")


def main() -> int:
    executable = executable_path()
    if not executable.is_file():
        raise SystemExit(f"Desktop executable does not exist: {executable}")
    port = available_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="wmrm-desktop-") as data_dir:
        process = subprocess.Popen(
            [
                str(executable),
                "--no-browser",
                "--port",
                str(port),
                "--data-dir",
                data_dir,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            health = wait_for_health(base_url, process)
            with urllib.request.urlopen(f"{base_url}/", timeout=2) as response:
                index = response.read().decode("utf-8")
            with urllib.request.urlopen(f"{base_url}/tasks", timeout=2) as response:
                spa_route = response.read().decode("utf-8")
            if health.get("status") != "ok" or "Watermark Remover" not in index:
                raise RuntimeError(
                    "Desktop bundle returned an invalid health or frontend response."
                )
            if spa_route != index:
                raise RuntimeError("Desktop bundle did not serve the Vue history fallback.")
            request_shutdown(base_url)
            process.wait(timeout=15)
            if process.returncode != 0:
                raise RuntimeError(f"Desktop process exited with code {process.returncode}.")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
    print(json.dumps({"executable": str(executable), "health": health}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
