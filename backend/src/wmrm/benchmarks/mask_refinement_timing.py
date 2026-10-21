from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
from pathlib import Path
from typing import Any

PROTOCOL_ID = "wmrm-mask-refinement-human-timing-v1"
WORKFLOWS = ("manual", "box", "refined")
MIN_PARTICIPANTS = 3
MIN_PAIRED_SAMPLES = 8
MAX_FAILURE_RATE = 0.10
MAX_REFINED_TO_MANUAL_MEDIAN_RATIO = 0.75
MAX_REFINED_TO_BOX_MEDIAN_RATIO = 0.90


class MaskRefinementTimingError(ValueError):
    pass


def describe_timing_protocol(
    manifest_path: Path, *, report_json: Path, report_markdown: Path
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise MaskRefinementTimingError("Unsupported corpus schema.")
    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise MaskRefinementTimingError("Corpus samples must be a list.")
    positives = [
        _timing_sample(manifest_path.parent, item) for item in samples if _is_positive(item)
    ]
    if len(positives) < MIN_PAIRED_SAMPLES:
        raise MaskRefinementTimingError(
            f"Timing protocol requires at least {MIN_PAIRED_SAMPLES} positive samples."
        )
    report = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "corpus_manifest": manifest_path.name,
        "corpus_sha256": _sha256(manifest_path),
        "positive_sample_count": len(positives),
        "workflows": list(WORKFLOWS),
        "design": {
            "task_order": "seeded three-block counterbalance",
            "tasks_per_participant": len(positives) * len(WORKFLOWS),
            "participant_identity": "one-way pseudonymous id; raw code is not stored",
            "expected_masks_visible_to_participant": False,
        },
        "thresholds": {
            "minimum_participants": MIN_PARTICIPANTS,
            "minimum_paired_samples": MIN_PAIRED_SAMPLES,
            "maximum_failure_rate": MAX_FAILURE_RATE,
            "maximum_refined_to_manual_median_ratio": (
                MAX_REFINED_TO_MANUAL_MEDIAN_RATIO
            ),
            "maximum_refined_to_box_median_ratio": MAX_REFINED_TO_BOX_MEDIAN_RATIO,
        },
        "summary": {
            "participant_count": 0,
            "trial_count": 0,
            "timing_gate": "fail",
            "release_claim_allowed": False,
        },
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_markdown.write_text(_protocol_markdown(report), encoding="utf-8")
    return report


def create_timing_session(
    manifest_path: Path,
    *,
    refined_predictions_path: Path,
    output: Path,
    participant_code: str,
    seed: int,
) -> dict[str, Any]:
    """Create a deterministic, counterbalanced task order without storing identity data."""
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != 1:
        raise MaskRefinementTimingError("Unsupported corpus schema.")
    samples = manifest.get("samples")
    if not isinstance(samples, list):
        raise MaskRefinementTimingError("Corpus samples must be a list.")
    positives = [
        _timing_sample(manifest_path.parent, item) for item in samples if _is_positive(item)
    ]
    if len(positives) < MIN_PAIRED_SAMPLES:
        raise MaskRefinementTimingError(
            f"Timing protocol requires at least {MIN_PAIRED_SAMPLES} positive samples."
        )
    if not participant_code.strip():
        raise MaskRefinementTimingError("Participant code must not be empty.")
    refined_predictions_path = refined_predictions_path.resolve()
    refiner, refined_masks = _refined_predictions(refined_predictions_path, positives)

    participant_id = hashlib.sha256(
        f"{PROTOCOL_ID}:{participant_code.strip()}".encode()
    ).hexdigest()[:16]
    rng = random.Random(seed)
    rng.shuffle(positives)
    workflow_offset = int(participant_id[:8], 16) % len(WORKFLOWS)
    tasks = []
    for block in range(len(WORKFLOWS)):
        for sample_index, sample in enumerate(positives):
            workflow = WORKFLOWS[(sample_index + block + workflow_offset) % len(WORKFLOWS)]
            task_key = f"{participant_id}:{seed}:{sample['sample_id']}:{workflow}"
            tasks.append(
                {
                    "task_id": hashlib.sha256(task_key.encode()).hexdigest()[:20],
                    "sample_id": sample["sample_id"],
                    "workflow": workflow,
                    "image_file": sample["image_file"],
                    "image_sha256": sample["image_sha256"],
                    "candidate_box": sample["candidate_box"],
                    "refined_mask_file": refined_masks[sample["sample_id"]]["file"],
                    "refined_mask_sha256": refined_masks[sample["sample_id"]]["sha256"],
                }
            )

    session = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "participant_id": participant_id,
        "seed": seed,
        "corpus_manifest": manifest_path.name,
        "corpus_sha256": _sha256(manifest_path),
        "refined_predictions": refined_predictions_path.name,
        "refined_predictions_sha256": _sha256(refined_predictions_path),
        "refiner": refiner,
        "instructions": {
            "start": "Start timing when the image and initial suggestion are visible.",
            "stop": "Stop timing after the final usable mask is confirmed.",
            "correction": "Record active editing time separately from total task time.",
            "failure": "Mark failed only when no usable mask can be completed; give a reason.",
            "blinding": "Do not reveal workflow names or expected masks to the participant.",
        },
        "tasks": tasks,
    }
    session["session_sha256"] = _session_digest(session)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return session


def _refined_predictions(
    path: Path, positives: list[dict[str, Any]]
) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    payload = _load_json(path)
    refiner = payload.get("refiner")
    if not isinstance(refiner, dict) or refiner.get("is_model_output") is not True:
        raise MaskRefinementTimingError("Timing sessions require real model predictions.")
    if refiner.get("automatic_download") is not False:
        raise MaskRefinementTimingError("Timing refiner must not download weights automatically.")
    metadata = {
        key: _required_text(refiner, key)
        for key in ("id", "model_id", "model_revision", "prompt_version", "device")
    }
    rows = payload.get("predictions")
    if not isinstance(rows, list):
        raise MaskRefinementTimingError("Refined predictions must contain sample rows.")
    by_id = {}
    for row in rows:
        if not isinstance(row, dict):
            raise MaskRefinementTimingError("Refined prediction rows must be objects.")
        sample_id = _required_text(row, "sample_id")
        if sample_id in by_id:
            raise MaskRefinementTimingError("Duplicate refined prediction row.")
        by_id[sample_id] = row
    masks = {}
    for sample in positives:
        sample_id = sample["sample_id"]
        row = by_id.get(sample_id)
        if row is None:
            raise MaskRefinementTimingError(f"Missing refined prediction: {sample_id}")
        relative = _required_text(row, "mask_file")
        mask_path = (path.parent / relative).resolve()
        if path.parent != mask_path and path.parent not in mask_path.parents:
            raise MaskRefinementTimingError(f"Refined mask leaves prediction root: {sample_id}")
        expected = _required_text(row, "mask_sha256")
        if not mask_path.is_file() or _sha256(mask_path) != expected:
            raise MaskRefinementTimingError(f"Refined mask integrity check failed: {sample_id}")
        masks[sample_id] = {"file": relative, "sha256": expected}
    return metadata, masks


def create_result_template(session_path: Path, *, output: Path) -> dict[str, Any]:
    session = _load_and_validate_session(session_path)
    result = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "participant_id": session["participant_id"],
        "session_sha256": session["session_sha256"],
        "trials": [
            {
                "task_id": task["task_id"],
                "total_seconds": None,
                "correction_seconds": None,
                "status": None,
                "failure_reason": None,
            }
            for task in session["tasks"]
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def audit_timing_sessions(
    pairs: list[tuple[Path, Path]],
    *,
    report_json: Path,
    report_markdown: Path,
) -> dict[str, Any]:
    if not pairs:
        raise MaskRefinementTimingError("At least one session/result pair is required.")
    participant_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    corpus_digests: set[str] = set()
    for session_path, result_path in pairs:
        session = _load_and_validate_session(session_path)
        result = _load_json(result_path)
        participant_id = session["participant_id"]
        if participant_id in participant_ids:
            raise MaskRefinementTimingError("Each participant may contribute only one session.")
        participant_ids.add(participant_id)
        corpus_digests.add(session["corpus_sha256"])
        _validate_result_header(session, result)
        tasks = {task["task_id"]: task for task in session["tasks"]}
        trials = result.get("trials")
        if not isinstance(trials, list) or len(trials) != len(tasks):
            raise MaskRefinementTimingError("Results must contain every session task exactly once.")
        seen: set[str] = set()
        for trial in trials:
            if not isinstance(trial, dict):
                raise MaskRefinementTimingError("Timing trials must be objects.")
            task_id = _required_text(trial, "task_id")
            if task_id in seen or task_id not in tasks:
                raise MaskRefinementTimingError("Results contain a duplicate or unknown task.")
            seen.add(task_id)
            task = tasks[task_id]
            records.append(_validate_trial(participant_id, task, trial))
    if len(corpus_digests) != 1:
        raise MaskRefinementTimingError("All sessions must use the same frozen corpus.")

    workflows = {name: _workflow_summary(records, name) for name in WORKFLOWS}
    paired_samples = _paired_sample_count(records)
    participant_gate = len(participant_ids) >= MIN_PARTICIPANTS
    paired_sample_gate = paired_samples >= MIN_PAIRED_SAMPLES
    failure_gate = all(item["failure_rate"] <= MAX_FAILURE_RATE for item in workflows.values())
    medians_available = all(item["total_median_seconds"] is not None for item in workflows.values())
    refined_vs_manual = _ratio(
        workflows["refined"]["total_median_seconds"],
        workflows["manual"]["total_median_seconds"],
    )
    refined_vs_box = _ratio(
        workflows["refined"]["total_median_seconds"],
        workflows["box"]["total_median_seconds"],
    )
    speed_gate = bool(
        medians_available
        and refined_vs_manual is not None
        and refined_vs_manual <= MAX_REFINED_TO_MANUAL_MEDIAN_RATIO
        and refined_vs_box is not None
        and refined_vs_box <= MAX_REFINED_TO_BOX_MEDIAN_RATIO
    )
    timing_gate = participant_gate and paired_sample_gate and failure_gate and speed_gate
    report = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "corpus_sha256": next(iter(corpus_digests)),
        "thresholds": {
            "minimum_participants": MIN_PARTICIPANTS,
            "minimum_paired_samples": MIN_PAIRED_SAMPLES,
            "maximum_failure_rate": MAX_FAILURE_RATE,
            "maximum_refined_to_manual_median_ratio": MAX_REFINED_TO_MANUAL_MEDIAN_RATIO,
            "maximum_refined_to_box_median_ratio": MAX_REFINED_TO_BOX_MEDIAN_RATIO,
        },
        "summary": {
            "participant_count": len(participant_ids),
            "paired_sample_count": paired_samples,
            "trial_count": len(records),
            "participant_gate": "pass" if participant_gate else "fail",
            "paired_sample_gate": "pass" if paired_sample_gate else "fail",
            "failure_gate": "pass" if failure_gate else "fail",
            "speed_gate": "pass" if speed_gate else "fail",
            "timing_gate": "pass" if timing_gate else "fail",
            "refined_to_manual_median_ratio": refined_vs_manual,
            "refined_to_box_median_ratio": refined_vs_box,
        },
        "workflows": workflows,
        "failures": [
            {
                "participant_id": row["participant_id"],
                "sample_id": row["sample_id"],
                "workflow": row["workflow"],
                "reason": row["failure_reason"],
            }
            for row in records
            if row["status"] == "failed"
        ],
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_markdown.write_text(_markdown(report), encoding="utf-8")
    return report


def _timing_sample(root: Path, sample: object) -> dict[str, Any]:
    if not isinstance(sample, dict):
        raise MaskRefinementTimingError("Corpus samples must be objects.")
    sample_id = _required_text(sample, "id")
    image_file = _required_text(sample, "file")
    image_path = (root / image_file).resolve()
    if root != image_path and root not in image_path.parents:
        raise MaskRefinementTimingError(f"Sample path leaves the corpus: {sample_id}")
    if not image_path.is_file() or _sha256(image_path) != _required_text(sample, "sha256"):
        raise MaskRefinementTimingError(f"Sample integrity check failed: {sample_id}")
    box = sample.get("candidate_box")
    if not isinstance(box, dict):
        raise MaskRefinementTimingError(f"Missing candidate box: {sample_id}")
    coordinates = {key: _required_number(box, key) for key in ("x0", "y0", "x1", "y1")}
    if not (0 <= coordinates["x0"] < coordinates["x1"] <= _required_number(sample, "width")):
        raise MaskRefinementTimingError(f"Invalid candidate box: {sample_id}")
    if not (0 <= coordinates["y0"] < coordinates["y1"] <= _required_number(sample, "height")):
        raise MaskRefinementTimingError(f"Invalid candidate box: {sample_id}")
    return {
        "sample_id": sample_id,
        "image_file": image_file,
        "image_sha256": _sha256(image_path),
        "candidate_box": coordinates,
    }


def _is_positive(sample: object) -> bool:
    return isinstance(sample, dict) and sample.get("pair_role") == "watermark_positive"


def _load_and_validate_session(path: Path) -> dict[str, Any]:
    session = _load_json(path)
    if session.get("schema_version") != 1 or session.get("protocol_id") != PROTOCOL_ID:
        raise MaskRefinementTimingError("Unsupported timing session schema.")
    if session.get("session_sha256") != _session_digest(session):
        raise MaskRefinementTimingError("Timing session digest mismatch.")
    _required_text(session, "participant_id")
    _required_text(session, "corpus_sha256")
    tasks = session.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise MaskRefinementTimingError("Timing session has no tasks.")
    task_ids = [_required_text(task, "task_id") for task in tasks if isinstance(task, dict)]
    if len(task_ids) != len(tasks) or len(task_ids) != len(set(task_ids)):
        raise MaskRefinementTimingError("Timing session task IDs must be unique.")
    return session


def _session_digest(session: dict[str, Any]) -> str:
    payload = {key: value for key, value in session.items() if key != "session_sha256"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _validate_result_header(session: dict[str, Any], result: dict[str, Any]) -> None:
    expected = {
        "schema_version": 1,
        "protocol_id": PROTOCOL_ID,
        "participant_id": session["participant_id"],
        "session_sha256": session["session_sha256"],
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise MaskRefinementTimingError("Result header does not match its timing session.")


def _validate_trial(
    participant_id: str, task: dict[str, Any], trial: dict[str, Any]
) -> dict[str, Any]:
    status = trial.get("status")
    if status not in {"completed", "failed"}:
        raise MaskRefinementTimingError("Trial status must be completed or failed.")
    total = _required_number(trial, "total_seconds")
    correction = _required_number(trial, "correction_seconds")
    if total <= 0 or correction < 0 or correction > total:
        raise MaskRefinementTimingError("Trial timing values are inconsistent.")
    reason = trial.get("failure_reason")
    if status == "failed" and (not isinstance(reason, str) or not reason.strip()):
        raise MaskRefinementTimingError("Failed trials require a failure reason.")
    if status == "completed" and reason not in {None, ""}:
        raise MaskRefinementTimingError("Completed trials cannot include a failure reason.")
    return {
        "participant_id": participant_id,
        "sample_id": task["sample_id"],
        "workflow": task["workflow"],
        "total_seconds": total,
        "correction_seconds": correction,
        "status": status,
        "failure_reason": reason.strip() if isinstance(reason, str) else None,
    }


def _workflow_summary(records: list[dict[str, Any]], workflow: str) -> dict[str, Any]:
    rows = [row for row in records if row["workflow"] == workflow]
    completed = [row for row in rows if row["status"] == "completed"]
    return {
        "trial_count": len(rows),
        "completed_count": len(completed),
        "failure_count": len(rows) - len(completed),
        "failure_rate": round((len(rows) - len(completed)) / len(rows), 6) if rows else 1.0,
        "total_median_seconds": _median(completed, "total_seconds"),
        "correction_median_seconds": _median(completed, "correction_seconds"),
    }


def _paired_sample_count(records: list[dict[str, Any]]) -> int:
    mapping: dict[str, set[str]] = {}
    for row in records:
        if row["status"] == "completed":
            mapping.setdefault(row["sample_id"], set()).add(row["workflow"])
    return sum(workflows == set(WORKFLOWS) for workflows in mapping.values())


def _median(rows: list[dict[str, Any]], field: str) -> float | None:
    return round(statistics.median(row[field] for row in rows), 6) if rows else None


def _ratio(numerator: object, denominator: object) -> float | None:
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return None
    return round(numerator / denominator, 6) if denominator > 0 else None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MaskRefinementTimingError(f"Cannot read JSON: {path}") from error
    if not isinstance(value, dict):
        raise MaskRefinementTimingError(f"JSON root must be an object: {path}")
    return value


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MaskRefinementTimingError(f"Missing required text field: {field}")
    return value


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MaskRefinementTimingError(f"Missing required number field: {field}")
    return float(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = [
        "| Workflow | Trials | Completed | Failures | Failure rate | "
        "Total median | Correction median |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in WORKFLOWS:
        item = report["workflows"][name]
        rows.append(
            f"| {name} | {item['trial_count']} | {item['completed_count']} | "
            f"{item['failure_count']} | {item['failure_rate']:.3f} | "
            f"{item['total_median_seconds'] or 'n/a'} | "
            f"{item['correction_median_seconds'] or 'n/a'} |"
        )
    return "\n".join(
        [
            "# Mask refinement human timing report",
            "",
            f"Protocol: `{report['protocol_id']}`",
            "",
            f"Timing gate: **{summary['timing_gate']}**",
            f"Participants: {summary['participant_count']} · paired samples: "
            f"{summary['paired_sample_count']} · trials: {summary['trial_count']}",
            f"Refined/manual median ratio: {summary['refined_to_manual_median_ratio']}",
            f"Refined/box median ratio: {summary['refined_to_box_median_ratio']}",
            "",
            *rows,
            "",
            "This report contains anonymous participant IDs only. Raw task timings must remain "
            "free of names, email addresses, device account names, and free-form notes.",
            "",
        ]
    )


def _protocol_markdown(report: dict[str, Any]) -> str:
    thresholds = report["thresholds"]
    return "\n".join(
        [
            "# Mask refinement human timing protocol",
            "",
            f"Protocol: `{report['protocol_id']}`",
            f"Frozen corpus SHA-256: `{report['corpus_sha256']}`",
            f"Positive samples: {report['positive_sample_count']} · workflows: "
            f"{', '.join(report['workflows'])}",
            "",
            "## Frozen gates",
            "",
            f"- Participants: at least {thresholds['minimum_participants']}",
            f"- Paired samples: at least {thresholds['minimum_paired_samples']}",
            f"- Failure rate per workflow: at most {thresholds['maximum_failure_rate']:.0%}",
            "- Refined/manual total-time median ratio: at most "
            f"{thresholds['maximum_refined_to_manual_median_ratio']:.0%}",
            "- Refined/box total-time median ratio: at most "
            f"{thresholds['maximum_refined_to_box_median_ratio']:.0%}",
            "",
            "No human timing evidence has been collected. Timing gate: **fail**. "
            "Release claim allowed: **false**.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare and audit blind mask timing sessions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    describe = subparsers.add_parser("describe")
    describe.add_argument("--manifest", type=Path, required=True)
    describe.add_argument("--report-json", type=Path, required=True)
    describe.add_argument("--report-md", type=Path, required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--manifest", type=Path, required=True)
    prepare.add_argument("--refined-predictions", type=Path, required=True)
    prepare.add_argument("--session", type=Path, required=True)
    prepare.add_argument("--results", type=Path, required=True)
    prepare.add_argument("--participant-code", required=True)
    prepare.add_argument("--seed", type=int, required=True)
    audit = subparsers.add_parser("audit")
    audit.add_argument("--pair", action="append", required=True, metavar="SESSION:RESULTS")
    audit.add_argument("--report-json", type=Path, required=True)
    audit.add_argument("--report-md", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "describe":
        describe_timing_protocol(
            args.manifest, report_json=args.report_json, report_markdown=args.report_md
        )
        return
    if args.command == "prepare":
        create_timing_session(
            args.manifest,
            refined_predictions_path=args.refined_predictions,
            output=args.session,
            participant_code=args.participant_code,
            seed=args.seed,
        )
        create_result_template(args.session, output=args.results)
        return
    pairs = []
    for value in args.pair:
        session, separator, results = value.partition(":")
        if not separator:
            parser.error("--pair must use SESSION:RESULTS")
        pairs.append((Path(session), Path(results)))
    audit_timing_sessions(pairs, report_json=args.report_json, report_markdown=args.report_md)


if __name__ == "__main__":
    main()
