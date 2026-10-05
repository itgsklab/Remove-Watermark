from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse


def mount_frontend(app: FastAPI, frontend_dir: Path) -> None:
    root = frontend_dir.resolve()
    index = root / "index.html"
    assets = root / "assets"
    if not index.is_file() or not assets.is_dir():
        raise RuntimeError(f"Frontend build is incomplete: {root}")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend(request: Request, frontend_path: str):
        if frontend_path == "api" or frontend_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "找不到该 API。",
                        "details": {},
                        "request_id": request.state.request_id,
                    }
                },
            )
        candidate = (root / frontend_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            candidate = index
        if candidate.is_file():
            cache_control = (
                "public, max-age=31536000, immutable"
                if candidate.is_relative_to(assets)
                else "no-store"
            )
            return FileResponse(
                candidate,
                headers={"Cache-Control": cache_control},
            )
        return FileResponse(index, headers={"Cache-Control": "no-store"})
