from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import wmrm.web as web
from wmrm.api.app import create_app
from wmrm.settings import Settings


def make_frontend(root: Path) -> Path:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text("<main>Watermark Remover</main>", encoding="utf-8")
    (assets / "app.js").write_text("console.log('wmrm')", encoding="utf-8")
    return root


def test_serves_production_frontend_and_spa_routes(tmp_path: Path) -> None:
    frontend = make_frontend(tmp_path / "frontend")
    settings = Settings(data_dir=tmp_path / "data", dev_cors=False)
    with TestClient(create_app(settings, frontend_dir=frontend)) as client:
        home = client.get("/")
        spa_route = client.get("/tasks")
        asset = client.get("/assets/app.js")
        missing_api = client.get("/api/v1/not-found")

    assert home.status_code == 200
    assert spa_route.text == home.text
    assert home.headers["cache-control"] == "no-store"
    assert "default-src 'self'" in home.headers["content-security-policy"]
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_api.status_code == 404
    assert missing_api.json()["error"]["code"] == "NOT_FOUND"


def test_resolves_configured_frontend_build(tmp_path: Path) -> None:
    frontend = make_frontend(tmp_path / "dist")
    assert web.resolve_frontend_dir(frontend) == frontend.resolve()
    assert web.resolve_frontend_dir(None, environ={"WMRM_FRONTEND_DIR": str(frontend)}) == (
        frontend.resolve()
    )


def test_rejects_incomplete_frontend_build(tmp_path: Path) -> None:
    incomplete = tmp_path / "dist"
    incomplete.mkdir()
    with pytest.raises(ValueError, match="No complete Vue production build"):
        web.resolve_frontend_dir(incomplete)


def test_web_settings_require_loopback_and_valid_port(tmp_path: Path) -> None:
    settings = web.web_settings(
        Settings(data_dir=tmp_path / "old"),
        port=9010,
        data_dir=tmp_path / "new",
    )
    assert settings.host == "127.0.0.1"
    assert settings.port == 9010
    assert settings.data_dir == tmp_path / "new"
    assert settings.dev_cors is False
    with pytest.raises(ValueError, match="port"):
        web.web_settings(settings, port=70000, data_dir=None)
    with pytest.raises(ValueError, match="127.0.0.1"):
        web.web_settings(Settings(host="0.0.0.0"), port=None, data_dir=None)


def test_main_serves_frontend_without_remote_shutdown(tmp_path: Path, monkeypatch) -> None:
    frontend = make_frontend(tmp_path / "dist")
    captured: dict[str, object] = {}

    def fake_run(app, **kwargs) -> None:
        captured["app"] = app
        captured.update(kwargs)

    monkeypatch.setattr(web.uvicorn, "run", fake_run)
    assert web.main(["--frontend-dir", str(frontend), "--port", "9011"]) == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9011
    with TestClient(captured["app"]) as client:
        assert client.get("/").status_code == 200
        assert client.post("/api/v1/system/shutdown").status_code == 405
