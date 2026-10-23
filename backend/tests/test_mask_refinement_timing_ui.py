import hashlib
import json
import shutil
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wmrm.benchmarks.mask_refinement_timing import (
    MaskRefinementTimingError,
    create_result_template,
    create_timing_session,
)
from wmrm.benchmarks.mask_refinement_timing_ui import (
    TimingSessionStore,
    create_timing_ui_app,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mask_refinement_confirmation_fourth"


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    predictions_root = tmp_path / "model"
    predictions_root.mkdir(parents=True)
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    rows = []
    for sample in manifest["samples"]:
        if sample["pair_role"] != "watermark_positive":
            continue
        source = FIXTURES / sample["expected_mask"]
        target = predictions_root / "masks" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        rows.append(
            {
                "sample_id": sample["id"],
                "mask_file": f"masks/{target.name}",
                "mask_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    predictions = predictions_root / "predictions.json"
    predictions.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "refiner": {
                    "id": "test-refiner",
                    "model_id": "test/model",
                    "model_revision": "0123456789abcdef",
                    "prompt_version": "frozen-test-v1",
                    "device": "cpu",
                    "is_model_output": True,
                    "automatic_download": False,
                },
                "predictions": rows,
            }
        )
    )
    session = tmp_path / "session.json"
    results = tmp_path / "results.json"
    create_timing_session(
        FIXTURES / "manifest.json",
        refined_predictions_path=predictions,
        output=session,
        participant_code="anonymous-operator",
        seed=20261021,
    )
    create_result_template(session, output=results)
    return session, results, predictions


def _store(tmp_path: Path) -> TimingSessionStore:
    session, results, predictions = _files(tmp_path)
    return TimingSessionStore(
        session_path=session,
        results_path=results,
        manifest_path=FIXTURES / "manifest.json",
        refined_predictions_path=predictions,
    )


def test_ui_exposes_only_blinded_current_task_and_security_headers(tmp_path: Path) -> None:
    store = _store(tmp_path)
    client = TestClient(create_timing_ui_app(store))

    page = client.get("/")
    state = client.get("/api/state").json()

    assert page.status_code == 200
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert "蒙版操作计时" in page.text
    assert "准备开始下一项任务" in page.text
    assert "点击后才会加载任务并启动总计时" in page.text
    assert store.active_started_at is None
    assert state["completed"] == 0
    assert state["total"] == 24
    assert state["task"]["method_label"] in {"A", "B", "C"}
    assert "workflow" not in state["task"]
    assert "sample_id" not in state["task"]
    assert "expected" not in json.dumps(state)
    assert client.get(state["task"]["image_url"]).status_code == 200
    if state["task"]["initialization"]["kind"] == "bitmap":
        assert client.get(state["task"]["initialization"]["mask_url"]).status_code == 200


def test_ui_persists_each_trial_and_resumes_to_completion(tmp_path: Path) -> None:
    store = _store(tmp_path)
    client = TestClient(create_timing_ui_app(store))

    for _ in range(24):
        state = client.get("/api/state").json()
        task_id = state["task"]["task_id"]
        assert client.post(f"/api/tasks/{task_id}/start").status_code == 200
        response = client.post(
            f"/api/tasks/{task_id}/complete",
            json={
                "status": "completed",
                "correction_seconds": 0,
                "edit_actions": 0,
                "failure_reason": None,
            },
        )
        assert response.status_code == 200

    final = client.get("/api/state").json()
    payload = json.loads(store.results_path.read_text())
    resumed = TimingSessionStore(
        session_path=store.session_path,
        results_path=store.results_path,
        manifest_path=store.manifest_path,
        refined_predictions_path=store.refined_predictions_path,
    )

    assert final["finished"] is True
    assert final["completed"] == 24
    assert all(row["status"] == "completed" for row in payload["trials"])
    assert all(row["total_seconds"] > 0 for row in payload["trials"])
    assert resumed.state()["finished"] is True


def test_ui_keeps_atomic_timing_results_private(tmp_path: Path) -> None:
    store = _store(tmp_path)
    client = TestClient(create_timing_ui_app(store))
    state = client.get("/api/state").json()
    task_id = state["task"]["task_id"]

    store.results_path.chmod(0o600)
    assert client.post(f"/api/tasks/{task_id}/start").status_code == 200
    response = client.post(
        f"/api/tasks/{task_id}/complete",
        json={
            "status": "completed",
            "correction_seconds": 0,
            "edit_actions": 0,
            "failure_reason": None,
        },
    )

    assert response.status_code == 200
    assert stat.S_IMODE(store.results_path.stat().st_mode) == 0o600


def test_ui_rejects_out_of_order_submission_and_missing_failure_reason(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    client = TestClient(create_timing_ui_app(store))
    state = client.get("/api/state").json()
    active_id = state["task"]["task_id"]
    other_id = next(task["task_id"] for task in store.tasks if task["task_id"] != active_id)
    payload = {
        "status": "failed",
        "correction_seconds": 0,
        "edit_actions": 0,
        "failure_reason": None,
    }

    assert client.post(f"/api/tasks/{other_id}/start").status_code == 409
    assert client.post(f"/api/tasks/{active_id}/start").status_code == 200
    assert client.post(f"/api/tasks/{other_id}/complete", json=payload).status_code == 409
    assert client.post(f"/api/tasks/{active_id}/complete", json=payload).status_code == 422
    payload["failure_reason"] = "private free-form note"
    assert client.post(f"/api/tasks/{active_id}/complete", json=payload).status_code == 422


def test_ui_rejects_predictions_that_do_not_match_frozen_session(tmp_path: Path) -> None:
    session, results, predictions = _files(tmp_path)
    predictions.write_text(predictions.read_text() + "\n")

    with pytest.raises(MaskRefinementTimingError, match="prediction digest"):
        TimingSessionStore(
            session_path=session,
            results_path=results,
            manifest_path=FIXTURES / "manifest.json",
            refined_predictions_path=predictions,
        )
