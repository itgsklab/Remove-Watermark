import hashlib
import json
import shutil
from pathlib import Path

import pytest

from wmrm.benchmarks.mask_refinement_timing import (
    PROTOCOL_ID,
    MaskRefinementTimingError,
    audit_timing_sessions,
    create_result_template,
    create_timing_session,
    describe_timing_protocol,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mask_refinement_confirmation_fourth"


def _prepare(tmp_path: Path, participant: str, seed: int) -> tuple[Path, Path]:
    root = tmp_path / participant
    session = root / "session.json"
    results = root / "results.json"
    predictions = _model_predictions(root / "model")
    create_timing_session(
        FIXTURES / "manifest.json",
        refined_predictions_path=predictions,
        output=session,
        participant_code=participant,
        seed=seed,
    )
    create_result_template(session, output=results)
    return session, results


def _model_predictions(root: Path) -> Path:
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    root.mkdir(parents=True, exist_ok=True)
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
    payload = {
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
    path = root / "predictions.json"
    path.write_text(json.dumps(payload))
    return path


def _complete(results_path: Path, *, manual: float, box: float, refined: float) -> None:
    result = json.loads(results_path.read_text())
    session = json.loads((results_path.parent / "session.json").read_text())
    workflows = {task["task_id"]: task["workflow"] for task in session["tasks"]}
    durations = {"manual": manual, "box": box, "refined": refined}
    for trial in result["trials"]:
        duration = durations[workflows[trial["task_id"]]]
        trial.update(
            {
                "total_seconds": duration,
                "correction_seconds": duration * 0.8,
                "status": "completed",
                "failure_reason": None,
            }
        )
    results_path.write_text(json.dumps(result))


def test_session_is_deterministic_counterbalanced_and_anonymous(tmp_path: Path) -> None:
    first, results = _prepare(tmp_path / "one", "participant-secret", 20261021)
    second, _ = _prepare(tmp_path / "two", "participant-secret", 20261021)
    first_payload = json.loads(first.read_text())
    second_payload = json.loads(second.read_text())

    assert first_payload == second_payload
    assert first_payload["protocol_id"] == PROTOCOL_ID
    assert first_payload["participant_id"] != "participant-secret"
    assert "participant-secret" not in first.read_text()
    assert len(first_payload["tasks"]) == 24
    assert {task["workflow"] for task in first_payload["tasks"]} == {
        "manual",
        "box",
        "refined",
    }
    assert len({task["task_id"] for task in first_payload["tasks"]}) == 24
    assert all(
        left["sample_id"] != right["sample_id"]
        for left, right in zip(first_payload["tasks"], first_payload["tasks"][1:], strict=False)
    )
    by_sample = {}
    for task in first_payload["tasks"]:
        by_sample.setdefault(task["sample_id"], set()).add(task["workflow"])
    assert all(workflows == {"manual", "box", "refined"} for workflows in by_sample.values())
    assert len(json.loads(results.read_text())["trials"]) == 24


def test_protocol_record_keeps_release_gate_closed_before_human_evidence(tmp_path: Path) -> None:
    report = describe_timing_protocol(
        FIXTURES / "manifest.json",
        report_json=tmp_path / "protocol.json",
        report_markdown=tmp_path / "protocol.md",
    )

    assert report["positive_sample_count"] == 8
    assert report["design"]["tasks_per_participant"] == 24
    assert report["summary"]["timing_gate"] == "fail"
    assert report["summary"]["release_claim_allowed"] is False


def test_audit_passes_only_with_three_complete_paired_sessions(tmp_path: Path) -> None:
    pairs = [_prepare(tmp_path, f"operator-{index}", index) for index in range(3)]
    for _, results in pairs:
        _complete(results, manual=100, box=70, refined=50)

    report = audit_timing_sessions(
        pairs,
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"] == {
        "participant_count": 3,
        "paired_sample_count": 8,
        "trial_count": 72,
        "participant_gate": "pass",
        "paired_sample_gate": "pass",
        "failure_gate": "pass",
        "speed_gate": "pass",
        "timing_gate": "pass",
        "refined_to_manual_median_ratio": 0.5,
        "refined_to_box_median_ratio": 0.714286,
    }
    assert "Timing gate: **pass**" in (tmp_path / "report.md").read_text()


def test_audit_keeps_gate_closed_for_insufficient_real_participants(tmp_path: Path) -> None:
    pair = _prepare(tmp_path, "one-person", 7)
    _complete(pair[1], manual=100, box=70, refined=50)

    report = audit_timing_sessions(
        [pair],
        report_json=tmp_path / "report.json",
        report_markdown=tmp_path / "report.md",
    )

    assert report["summary"]["participant_gate"] == "fail"
    assert report["summary"]["timing_gate"] == "fail"


def test_audit_rejects_tampered_or_inconsistent_evidence(tmp_path: Path) -> None:
    session, results = _prepare(tmp_path, "operator", 3)
    payload = json.loads(results.read_text())
    payload["trials"][0].update(
        {
            "total_seconds": 5,
            "correction_seconds": 6,
            "status": "completed",
            "failure_reason": None,
        }
    )
    results.write_text(json.dumps(payload))

    with pytest.raises(MaskRefinementTimingError, match="inconsistent"):
        audit_timing_sessions(
            [(session, results)],
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )


def test_failed_trial_requires_reason(tmp_path: Path) -> None:
    session, results = _prepare(tmp_path, "operator", 3)
    payload = json.loads(results.read_text())
    for trial in payload["trials"]:
        trial.update(
            {
                "total_seconds": 5,
                "correction_seconds": 4,
                "status": "completed",
                "failure_reason": None,
            }
        )
    payload["trials"][0]["status"] = "failed"
    results.write_text(json.dumps(payload))

    with pytest.raises(MaskRefinementTimingError, match="failure reason"):
        audit_timing_sessions(
            [(session, results)],
            report_json=tmp_path / "report.json",
            report_markdown=tmp_path / "report.md",
        )
