import hashlib
import json
import shutil
import stat
from pathlib import Path

import pytest

from wmrm.benchmarks.mask_refinement_timing import MaskRefinementTimingError
from wmrm.benchmarks.mask_refinement_timing_collect import (
    audit_collection,
    collection_status,
    create_collection_run,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mask_refinement_confirmation_fourth"


def _predictions(root: Path) -> Path:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    rows = []
    for sample in manifest["samples"]:
        if sample["pair_role"] != "watermark_positive":
            continue
        source = FIXTURES / sample["expected_mask"]
        target = root / "masks" / source.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        rows.append(
            {
                "sample_id": sample["id"],
                "mask_file": f"masks/{target.name}",
                "mask_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    path = root / "predictions.json"
    path.write_text(
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
    return path


def _finish(run: dict[str, object]) -> None:
    session = json.loads(Path(run["session"]).read_text())
    results_path = Path(run["results"])
    results = json.loads(results_path.read_text())
    workflows = {task["task_id"]: task["workflow"] for task in session["tasks"]}
    durations = {"manual": 100, "box": 70, "refined": 50}
    for trial in results["trials"]:
        total = durations[workflows[trial["task_id"]]]
        trial.update(
            {
                "total_seconds": total,
                "correction_seconds": total * 0.8,
                "status": "completed",
                "failure_reason": None,
            }
        )
    results_path.write_text(json.dumps(results))


def test_collection_creates_anonymous_private_run(tmp_path: Path) -> None:
    predictions = _predictions(tmp_path / "model")
    root = tmp_path / "collection"
    run = create_collection_run(
        FIXTURES / "manifest.json",
        refined_predictions_path=predictions,
        collection_root=root,
        seed=17,
        participant_code="never-persist-this-code",
    )

    combined = Path(run["session"]).read_text() + Path(run["results"]).read_text()
    rows = collection_status(root)

    assert "never-persist-this-code" not in combined
    assert Path(run["session"]).parent.name == run["participant_id"]
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(Path(run["session"]).stat().st_mode) == 0o600
    assert rows[0]["completed"] == 0
    assert rows[0]["total"] == 24
    assert rows[0]["finished"] is False


def test_collection_audit_refuses_incomplete_run(tmp_path: Path) -> None:
    run = create_collection_run(
        FIXTURES / "manifest.json",
        refined_predictions_path=_predictions(tmp_path / "model"),
        collection_root=tmp_path / "collection",
        seed=18,
        participant_code="participant-one",
    )

    with pytest.raises(MaskRefinementTimingError, match="must be complete"):
        audit_collection(
            Path(run["session"]).parent.parent,
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_collection_audits_all_complete_runs(tmp_path: Path) -> None:
    predictions = _predictions(tmp_path / "model")
    root = tmp_path / "collection"
    runs = [
        create_collection_run(
            FIXTURES / "manifest.json",
            refined_predictions_path=predictions,
            collection_root=root,
            seed=index,
            participant_code=f"participant-{index}",
        )
        for index in range(3)
    ]
    for run in runs:
        _finish(run)

    report = audit_collection(
        root,
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"]["participant_count"] == 3
    assert report["summary"]["trial_count"] == 72
    assert report["summary"]["timing_gate"] == "pass"
    assert all(row["finished"] for row in collection_status(root))
