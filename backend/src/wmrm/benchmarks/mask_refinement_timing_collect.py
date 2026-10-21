from __future__ import annotations

import argparse
import json
import secrets
import shutil
from pathlib import Path
from typing import Any

from wmrm.benchmarks.mask_refinement_timing import (
    MaskRefinementTimingError,
    _load_and_validate_session,
    _load_json,
    _validate_result_header,
    audit_timing_sessions,
    create_result_template,
    create_timing_session,
)


def create_collection_run(
    manifest_path: Path,
    *,
    refined_predictions_path: Path,
    collection_root: Path,
    seed: int | None = None,
    participant_code: str | None = None,
) -> dict[str, Any]:
    """Create one anonymous local run without persisting the participant code."""
    collection_root = collection_root.resolve()
    collection_root.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(collection_root, 0o700)
    secret_code = participant_code or secrets.token_urlsafe(32)
    session_seed = seed if seed is not None else secrets.randbits(63)
    staging = collection_root / f".pending-{secrets.token_hex(8)}"
    staging.mkdir(mode=0o700)
    session_path = staging / "session.json"
    results_path = staging / "results.json"
    try:
        session = create_timing_session(
            manifest_path,
            refined_predictions_path=refined_predictions_path,
            output=session_path,
            participant_code=secret_code,
            seed=session_seed,
        )
        create_result_template(session_path, output=results_path)
        participant_id = session["participant_id"]
        run_root = collection_root / participant_id
        if run_root.exists():
            raise MaskRefinementTimingError("Anonymous participant session already exists.")
        staging.replace(run_root)
        _restrict_permissions(run_root, 0o700)
        _restrict_permissions(run_root / "session.json", 0o600)
        _restrict_permissions(run_root / "results.json", 0o600)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "participant_id": participant_id,
        "seed": session_seed,
        "session": run_root / "session.json",
        "results": run_root / "results.json",
    }


def collection_status(collection_root: Path) -> list[dict[str, Any]]:
    collection_root = collection_root.resolve()
    if not collection_root.is_dir():
        return []
    rows = []
    for run_root in sorted(collection_root.iterdir()):
        if not run_root.is_dir() or run_root.name.startswith("."):
            continue
        session_path = run_root / "session.json"
        results_path = run_root / "results.json"
        if not session_path.is_file() or not results_path.is_file():
            raise MaskRefinementTimingError(
                f"Collection run is missing session.json or results.json: {run_root.name}"
            )
        session = _load_and_validate_session(session_path)
        results = _load_json(results_path)
        _validate_result_header(session, results)
        if session["participant_id"] != run_root.name:
            raise MaskRefinementTimingError(
                f"Collection directory does not match participant ID: {run_root.name}"
            )
        tasks = session["tasks"]
        trials = results.get("trials")
        if not isinstance(trials, list) or len(trials) != len(tasks):
            raise MaskRefinementTimingError(
                f"Collection result count is invalid: {run_root.name}"
            )
        expected = [task["task_id"] for task in tasks]
        actual = [trial.get("task_id") for trial in trials if isinstance(trial, dict)]
        if actual != expected:
            raise MaskRefinementTimingError(
                f"Collection result task order is invalid: {run_root.name}"
            )
        completed = sum(trial.get("status") in {"completed", "failed"} for trial in trials)
        rows.append(
            {
                "participant_id": session["participant_id"],
                "completed": completed,
                "total": len(tasks),
                "finished": completed == len(tasks),
                "session": session_path,
                "results": results_path,
            }
        )
    return rows


def audit_collection(
    collection_root: Path, *, report_json: Path, report_markdown: Path
) -> dict[str, Any]:
    rows = collection_status(collection_root)
    if not rows:
        raise MaskRefinementTimingError("No participant sessions were found.")
    incomplete = [row["participant_id"] for row in rows if not row["finished"]]
    if incomplete:
        raise MaskRefinementTimingError(
            "Every participant session must be complete before audit: " + ", ".join(incomplete)
        )
    return audit_timing_sessions(
        [(row["session"], row["results"]) for row in rows],
        report_json=report_json,
        report_markdown=report_markdown,
    )


def _restrict_permissions(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError as error:
        raise MaskRefinementTimingError(
            f"Cannot restrict collection permissions: {path}"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordinate anonymous mask timing collection.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("new", help="Create one anonymous participant session.")
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--refined-predictions", type=Path, required=True)
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--seed", type=int)
    status = subparsers.add_parser("status", help="Show local collection progress.")
    status.add_argument("--root", type=Path, required=True)
    audit = subparsers.add_parser("audit", help="Audit every completed session in the root.")
    audit.add_argument("--root", type=Path, required=True)
    audit.add_argument("--report-json", type=Path, required=True)
    audit.add_argument("--report-md", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "new":
            run = create_collection_run(
                args.manifest,
                refined_predictions_path=args.refined_predictions,
                collection_root=args.root,
                seed=args.seed,
            )
            print(f"Anonymous participant: {run['participant_id']}")
            print(f"Session: {run['session']}")
            print(f"Results: {run['results']}")
            return 0
        if args.command == "status":
            rows = collection_status(args.root)
            print(
                json.dumps(
                    [
                        {
                            "participant_id": row["participant_id"],
                            "completed": row["completed"],
                            "total": row["total"],
                            "finished": row["finished"],
                        }
                        for row in rows
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        audit_collection(
            args.root, report_json=args.report_json, report_markdown=args.report_md
        )
        return 0
    except MaskRefinementTimingError as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
