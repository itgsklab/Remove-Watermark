from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from wmrm.api.app import create_app
from wmrm.settings import Settings, load_settings

LOOPBACK_HOST = "127.0.0.1"


def frontend_candidates(environ: dict[str, str] | None = None) -> list[Path]:
    values = os.environ if environ is None else environ
    candidates: list[Path] = []
    if configured := values.get("WMRM_FRONTEND_DIR"):
        candidates.append(Path(configured).expanduser())
    candidates.append(Path.cwd() / "frontend" / "dist")
    source_root = Path(__file__).resolve().parents[3]
    candidates.append(source_root / "frontend" / "dist")
    return candidates


def resolve_frontend_dir(
    configured: Path | None,
    *,
    environ: dict[str, str] | None = None,
) -> Path:
    candidates = (
        [configured.expanduser()] if configured is not None else frontend_candidates(environ)
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "index.html").is_file() and (resolved / "assets").is_dir():
            return resolved
    checked = ", ".join(str(path) for path in candidates)
    raise ValueError(f"未找到完整的 Vue 生产构建。已检查：{checked}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="启动由 FastAPI 同源提供的 Watermark Remover Web 界面。"
    )
    parser.add_argument("--frontend-dir", type=Path, help="Vue 生产构建目录。")
    parser.add_argument("--port", type=int, help="本地监听端口，默认读取 WMRM_PORT。")
    parser.add_argument("--data-dir", type=Path, help="覆盖本地数据目录。")
    return parser


def web_settings(base: Settings, *, port: int | None, data_dir: Path | None) -> Settings:
    selected_port = base.port if port is None else port
    if not 1 <= selected_port <= 65535:
        raise ValueError("端口必须在 1 到 65535 之间。")
    if base.host != LOOPBACK_HOST:
        raise ValueError("Web 服务当前只允许监听 127.0.0.1。")
    updates: dict[str, object] = {
        "host": LOOPBACK_HOST,
        "port": selected_port,
        "dev_cors": False,
        "worker_start_method": "spawn",
    }
    if data_dir is not None:
        updates["data_dir"] = data_dir.expanduser()
    return base.model_copy(update=updates)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        frontend_dir = resolve_frontend_dir(args.frontend_dir)
        settings = web_settings(load_settings(), port=args.port, data_dir=args.data_dir)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    app = create_app(settings, frontend_dir=frontend_dir)
    print(f"Watermark Remover Web: http://{LOOPBACK_HOST}:{settings.port}/")
    try:
        uvicorn.run(
            app,
            host=LOOPBACK_HOST,
            port=settings.port,
            log_level="info",
            access_log=False,
        )
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
