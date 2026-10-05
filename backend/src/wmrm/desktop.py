from __future__ import annotations

import argparse
import os
import platform
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from time import monotonic, sleep

import uvicorn

from wmrm.api.app import create_app
from wmrm.settings import Settings

LOOPBACK_HOST = "127.0.0.1"


def desktop_data_dir(
    *,
    system: str | None = None,
    home: Path | None = None,
    environ: dict[str, str] | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    if configured := values.get("WMRM_DATA_DIR"):
        return Path(configured).expanduser()
    platform_name = system or platform.system()
    user_home = home or Path.home()
    if platform_name == "Darwin":
        return user_home / "Library" / "Application Support" / "Watermark Remover"
    if platform_name == "Windows":
        base = Path(values.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
        return base / "Watermark Remover"
    base = Path(values.get("XDG_DATA_HOME", user_home / ".local" / "share"))
    return base / "watermark-remover"


def bundled_frontend_dir() -> Path | None:
    candidates = [
        Path(__file__).resolve().parent / "static",
        Path(sys.executable).resolve().parent / "wmrm" / "static",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file():
            return candidate
    return None


def bind_loopback_socket(port: int) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((LOOPBACK_HOST, port))
    listener.listen(2048)
    return listener


def _open_when_ready(server: uvicorn.Server, url: str, enabled: bool) -> None:
    if not enabled:
        return
    deadline = monotonic() + 15
    while not server.started and not server.should_exit and monotonic() < deadline:
        sleep(0.05)
    if server.started and not server.should_exit:
        webbrowser.open(url, new=1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="启动 Watermark Remover 本地桌面服务。")
    parser.add_argument("--port", type=int, default=0, help="本地端口；0 表示自动选择。")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器。")
    parser.add_argument("--frontend-dir", type=Path, help="覆盖前端生产构建目录。")
    parser.add_argument("--data-dir", type=Path, help="覆盖本地数据目录。")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise SystemExit("--port 必须在 0 到 65535 之间。")
    frontend_dir = args.frontend_dir or bundled_frontend_dir()
    if frontend_dir is None:
        raise SystemExit("未找到前端生产构建；请先运行打包脚本或传入 --frontend-dir。")
    listener = bind_loopback_socket(args.port)
    actual_port = int(listener.getsockname()[1])
    data_dir = args.data_dir.expanduser() if args.data_dir else desktop_data_dir()
    settings = Settings(
        host=LOOPBACK_HOST,
        port=actual_port,
        data_dir=data_dir,
        dev_cors=False,
        worker_start_method="spawn",
    )
    server: uvicorn.Server | None = None

    def request_shutdown() -> None:
        if server is not None:
            server.should_exit = True

    app = create_app(
        settings,
        frontend_dir=frontend_dir,
        shutdown_callback=request_shutdown,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=LOOPBACK_HOST,
            port=actual_port,
            log_level="info",
            access_log=False,
        )
    )
    url = f"http://{LOOPBACK_HOST}:{actual_port}/"
    opener = threading.Thread(
        target=_open_when_ready,
        args=(server, url, not args.no_browser),
        name="wmrm-browser-opener",
        daemon=True,
    )
    opener.start()
    try:
        try:
            server.run(sockets=[listener])
        except KeyboardInterrupt:
            pass
    finally:
        listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
