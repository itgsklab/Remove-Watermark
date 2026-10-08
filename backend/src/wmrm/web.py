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
    raise ValueError(f"No complete Vue production build was found. Checked: {checked}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Serve the Watermark Remover Vue interface and API from FastAPI."
    )
    parser.add_argument("--frontend-dir", type=Path, help="Vue production build directory.")
    parser.add_argument("--port", type=int, help="Loopback port; defaults to WMRM_PORT.")
    parser.add_argument("--data-dir", type=Path, help="Override the local data directory.")
    return parser


def web_settings(base: Settings, *, port: int | None, data_dir: Path | None) -> Settings:
    selected_port = base.port if port is None else port
    if not 1 <= selected_port <= 65535:
        raise ValueError("The port must be between 1 and 65535.")
    if base.host != LOOPBACK_HOST:
        raise ValueError("The Web service may only listen on 127.0.0.1.")
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
