import os
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep

from docx_compat import PROFILES, make_compatibility_docx
from fastapi.testclient import TestClient
from sqlalchemy import delete

from wmrm.api.app import create_app
from wmrm.persistence.database import ArtifactRecord, AssetRecord, TaskRecord
from wmrm.settings import Settings


def slow_task_process(request, result_queue, cancel_event) -> None:
    marker = Path(request["preview_path"]).parent / "worker.pid"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(os.getpid()))
    while not cancel_event.is_set():
        sleep(0.01)
    result_queue.put({"status": "cancelled", "worker_pid": os.getpid()})


def crashing_task_process(request, result_queue, cancel_event) -> None:
    os._exit(7)


def stubborn_task_process(request, result_queue, cancel_event) -> None:
    marker = Path(request["preview_path"]).parent / "stubborn.pid"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(os.getpid()))
    sleep(10)


def test_running_task_can_be_cancelled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("wmrm.application.tasks.run_task_process", slow_task_process)
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        task = _create_task(client)
        marker = app.state.assets.data_dir / "artifacts" / task["id"] / "worker.pid"
        deadline = monotonic() + 10
        while not marker.exists() and monotonic() < deadline:
            sleep(0.01)
        assert marker.exists()
        assert int(marker.read_text()) != os.getpid()
        response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
        assert response.status_code == 200
        cancelled = _wait_for_status(client, task["id"], {"cancelled"})
        assert cancelled["stage"] == "任务已取消"
        assert cancelled["artifacts"] == []
        assert not (app.state.assets.data_dir / "artifacts" / task["id"]).exists()


def test_cancel_terminates_unresponsive_worker(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("wmrm.application.tasks.run_task_process", stubborn_task_process)
    app = create_app(_settings(tmp_path))
    app.state.tasks.cancel_grace_seconds = 0.1
    with TestClient(app) as client:
        task = _create_task(client)
        marker = app.state.assets.data_dir / "artifacts" / task["id"] / "stubborn.pid"
        deadline = monotonic() + 10
        while not marker.exists() and monotonic() < deadline:
            sleep(0.01)
        assert marker.exists()

        response = client.post(f"/api/v1/tasks/{task['id']}/cancel")
        assert response.status_code == 200
        cancelled = _wait_for_status(client, task["id"], {"cancelled"})
        assert cancelled["artifacts"] == []
        assert not (app.state.assets.data_dir / "artifacts" / task["id"]).exists()


def test_worker_crash_is_reported_as_task_failure(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("wmrm.application.tasks.run_task_process", crashing_task_process)
    settings = _settings(tmp_path)
    settings.worker_start_method = "spawn"
    app = create_app(settings)
    with TestClient(app) as client:
        task = _create_task(client)
        failed = _wait_for_status(client, task["id"], {"failed"})
        assert failed["stage"] == "处理失败"
        assert failed["error"]["code"] == "PROCESSING_FAILED"
        assert "exit code 7" in failed["error"]["message"]
        assert failed["artifacts"] == []


def test_restart_recovers_interrupted_task(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first_app = create_app(settings)
    with TestClient(first_app) as client:
        task = _create_task(client)
        completed = _wait_for_status(client, task["id"], {"succeeded"})
        assert completed["artifacts"]
        with first_app.state.database.session_factory() as session:
            record = session.get(TaskRecord, task["id"])
            assert record is not None
            record.status = "running"
            record.stage = "模拟服务中断"
            record.progress = 0.5
            session.execute(
                delete(ArtifactRecord).where(ArtifactRecord.task_id == task["id"])
            )
            session.commit()
        shutil.rmtree(
            first_app.state.assets.data_dir / "artifacts" / task["id"],
            ignore_errors=True,
        )

    second_app = create_app(settings)
    with TestClient(second_app) as client:
        recovered = _wait_for_status(client, task["id"], {"succeeded"})
        assert recovered["artifacts"]
        listed = client.get("/api/v1/tasks")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == task["id"]


def test_retention_cleanup_removes_expired_files_but_keeps_task_metadata(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        task = _wait_for_status(client, _create_task(client)["id"], {"succeeded"})
        unused = client.post(
            "/api/v1/assets", files={"file": ("unused.pdf", b"%PDF-1.7\n%%EOF")}
        ).json()
        now = datetime.now(UTC)
        expired = now - timedelta(days=40)
        with app.state.database.session_factory() as session:
            task_record = session.get(TaskRecord, task["id"])
            asset_record = session.get(AssetRecord, unused["id"])
            assert task_record is not None and asset_record is not None
            task_record.updated_at = expired
            asset_record.created_at = expired
            session.commit()
        temporary = app.state.assets.tmp_root / "abandoned.tmp"
        temporary.write_bytes(b"temporary")
        old_timestamp = (now - timedelta(days=2)).timestamp()
        os.utime(temporary, (old_timestamp, old_timestamp))

        summary = app.state.retention.cleanup(now)
        assert summary.artifacts == 1
        assert summary.assets == 1
        assert summary.temporary_files == 1
        retained = client.get(f"/api/v1/tasks/{task['id']}").json()
        assert retained["status"] == "succeeded"
        assert retained["artifacts"] == []
        assert "保留策略清理" in retained["stage"]
        assert client.get(f"/api/v1/assets/{unused['id']}").status_code == 404


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        max_upload_bytes=1024 * 1024,
        docx_preview_enabled=False,
        worker_start_method="forkserver",
    )


def _create_task(client: TestClient) -> dict:
    source = make_compatibility_docx(PROFILES[0], ("DRAFT",))
    asset = client.post(
        "/api/v1/assets", files={"file": ("lifecycle.docx", source)}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "watermark_text": "DRAFT"},
    ).json()
    plan = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": asset["id"],
            "asset_sha256": asset["sha256"],
            "analysis_id": analysis["id"],
            "operations": [
                {
                    "candidate_id": analysis["candidates"][0]["candidate_id"],
                    "strategy": "object",
                }
            ],
        },
    ).json()
    response = client.post("/api/v1/tasks", json={"plan_id": plan["id"]})
    assert response.status_code == 202
    return response.json()


def _wait_for_status(client: TestClient, task_id: str, expected: set[str]) -> dict:
    deadline = monotonic() + 10
    while monotonic() < deadline:
        task = client.get(f"/api/v1/tasks/{task_id}").json()
        if task["status"] in expected:
            return task
        sleep(0.02)
    raise AssertionError(f"task {task_id} did not reach {expected}")
