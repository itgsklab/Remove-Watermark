from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import wmrm.desktop as desktop
from wmrm.api.app import create_app
from wmrm.desktop import (
    LOOPBACK_HOST,
    _open_when_ready,
    bind_loopback_socket,
    bundled_frontend_dir,
    desktop_data_dir,
)
from wmrm.settings import Settings


def make_frontend(root: Path) -> Path:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Desktop UI</title>", encoding="utf-8")
    (root / "assets" / "app.js").write_text("window.ready = true", encoding="utf-8")
    return root


def test_serves_production_frontend_and_spa_routes(tmp_path: Path) -> None:
    frontend = make_frontend(tmp_path / "frontend")
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            docx_preview_enabled=False,
            pdf_preview_enabled=False,
            worker_start_method="forkserver",
        ),
        frontend_dir=frontend,
    )

    with TestClient(app) as client:
        index = client.get("/")
        spa_route = client.get("/tasks")
        asset = client.get("/assets/app.js")
        health = client.get("/api/v1/health")
        missing_api = client.get("/api/v1/not-real")

    assert index.status_code == 200
    assert "Desktop UI" in index.text
    assert index.headers["cache-control"] == "no-store"
    assert index.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in index.headers["content-security-policy"]
    assert spa_route.text == index.text
    assert asset.text == "window.ready = true"
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert health.json()["status"] == "ok"
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "NOT_FOUND"


def test_desktop_shutdown_is_explicit_and_same_origin(tmp_path: Path) -> None:
    frontend = make_frontend(tmp_path / "frontend")
    shutdown_requested: list[bool] = []
    app = create_app(
        Settings(data_dir=tmp_path / "data", worker_start_method="forkserver"),
        frontend_dir=frontend,
        shutdown_callback=lambda: shutdown_requested.append(True),
    )

    with TestClient(app) as client:
        capabilities = client.get("/api/v1/capabilities")
        rejected = client.post(
            "/api/v1/system/shutdown",
            headers={"Origin": "https://untrusted.example"},
        )
        accepted = client.post(
            "/api/v1/system/shutdown",
            headers={"Origin": "http://testserver"},
        )

    assert capabilities.json()["desktop_mode"] is True
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CROSS_ORIGIN_REQUEST"
    assert accepted.status_code == 202
    assert shutdown_requested == [True]


def test_source_server_does_not_expose_shutdown(client: TestClient) -> None:
    response = client.post("/api/v1/system/shutdown")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SHUTDOWN_NOT_AVAILABLE"


def test_rejects_incomplete_frontend_build(tmp_path: Path) -> None:
    incomplete = tmp_path / "frontend"
    incomplete.mkdir()
    try:
        create_app(
            Settings(data_dir=tmp_path / "data", worker_start_method="forkserver"),
            frontend_dir=incomplete,
        )
    except RuntimeError as error:
        assert "Frontend build is incomplete" in str(error)
    else:
        raise AssertionError("incomplete frontend should be rejected")


def test_desktop_data_dir_is_platform_specific(tmp_path: Path) -> None:
    assert desktop_data_dir(system="Darwin", home=tmp_path, environ={}) == (
        tmp_path / "Library" / "Application Support" / "Watermark Remover"
    )
    assert desktop_data_dir(system="Linux", home=tmp_path, environ={}) == (
        tmp_path / ".local" / "share" / "watermark-remover"
    )
    assert desktop_data_dir(
        system="Windows",
        home=tmp_path,
        environ={"LOCALAPPDATA": str(tmp_path / "Local")},
    ) == (tmp_path / "Local" / "Watermark Remover")
    assert desktop_data_dir(
        system="Linux", home=tmp_path, environ={"WMRM_DATA_DIR": "~/custom-wmrm"}
    ) == Path("~/custom-wmrm").expanduser()


def test_loopback_socket_reserves_an_ephemeral_port() -> None:
    listener = bind_loopback_socket(0)
    try:
        host, port = listener.getsockname()
        assert host == LOOPBACK_HOST
        assert port > 0
    finally:
        listener.close()


def test_finds_frontend_beside_desktop_module(tmp_path: Path, monkeypatch) -> None:
    module_dir = tmp_path / "wmrm"
    make_frontend(module_dir / "static")
    monkeypatch.setattr(desktop, "__file__", str(module_dir / "desktop.py"))

    assert bundled_frontend_dir() == module_dir / "static"


def test_browser_opens_only_after_server_is_ready(monkeypatch) -> None:
    opened: list[tuple[str, int]] = []
    monkeypatch.setattr(desktop.webbrowser, "open", lambda url, new: opened.append((url, new)))
    server = SimpleNamespace(started=True, should_exit=False)

    _open_when_ready(server, "http://127.0.0.1:1234/", True)
    _open_when_ready(server, "http://127.0.0.1:1234/", False)

    assert opened == [("http://127.0.0.1:1234/", 1)]


def test_desktop_main_builds_app_around_reserved_socket(tmp_path: Path, monkeypatch) -> None:
    frontend = make_frontend(tmp_path / "frontend")
    captured: dict[str, object] = {}

    class FakeServer:
        started = False
        should_exit = False

        def __init__(self, config) -> None:
            captured["config"] = config

        def run(self, *, sockets) -> None:
            captured["socket"] = sockets[0]
            captured["app"] = captured["config"].app

    monkeypatch.setattr(desktop.uvicorn, "Server", FakeServer)

    result = desktop.main(
        [
            "--no-browser",
            "--frontend-dir",
            str(frontend),
            "--data-dir",
            str(tmp_path / "data"),
        ]
    )

    assert result == 0
    assert captured["config"].host == LOOPBACK_HOST
    assert captured["app"].state.settings.data_dir == tmp_path / "data"


def test_desktop_main_rejects_invalid_port() -> None:
    with pytest.raises(SystemExit, match="--port"):
        desktop.main(["--port", "70000"])
