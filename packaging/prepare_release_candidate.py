from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import verify_release_evidence as evidence

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "packaging" / "cli-contract-v1.json"
GENERATED_METADATA = (
    Path("docs/THIRD_PARTY_DEPENDENCIES.md"),
    Path("docs/release/sbom.spdx.json"),
)
PUBLIC_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
RC_VERSION_PATTERN = re.compile(r"(?P<public>\d+\.\d+\.\d+)rc(?P<number>[1-9]\d*)")


class CandidateError(RuntimeError):
    pass


@dataclass(frozen=True)
class VersionSource:
    path: Path
    flavor: str
    expected_count: int = 1


VERSION_SOURCES = (
    VersionSource(Path("backend/pyproject.toml"), "python"),
    VersionSource(Path("backend/src/wmrm/__init__.py"), "python"),
    VersionSource(Path("backend/src/wmrm/settings.py"), "python"),
    VersionSource(Path("packaging/cli-contract-v1.json"), "python"),
    VersionSource(Path("frontend/package.json"), "npm"),
    VersionSource(Path("frontend/package-lock.json"), "npm", expected_count=2),
)


def git_value(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def git_is_clean() -> bool:
    return not git_value("status", "--porcelain")


def npm_version(python_version: str, public_version: str) -> str:
    if python_version == f"{public_version}.dev0":
        return f"{public_version}-dev"
    match = RC_VERSION_PATTERN.fullmatch(python_version)
    if match and match["public"] == public_version:
        return f"{public_version}-rc.{match['number']}"
    raise CandidateError(f"Unsupported Python release-line version: {python_version}")


def target_versions(contract: dict[str, Any], rc_number: int) -> tuple[str, str, str, str]:
    public_version = contract.get("target_public_version")
    current_python = contract.get("development_version")
    if not isinstance(public_version, str) or not PUBLIC_VERSION_PATTERN.fullmatch(public_version):
        raise CandidateError("The CLI contract has an invalid target public version.")
    if not isinstance(current_python, str):
        raise CandidateError("The CLI contract has an invalid development version.")
    if rc_number < 1:
        raise CandidateError("The release-candidate number must be positive.")

    current_match = RC_VERSION_PATTERN.fullmatch(current_python)
    if current_python != f"{public_version}.dev0":
        if not current_match or current_match["public"] != public_version:
            raise CandidateError("The current version is outside the target release line.")
        if rc_number <= int(current_match["number"]):
            raise CandidateError("The next release-candidate number must increase.")

    current_npm = npm_version(current_python, public_version)
    target_python = f"{public_version}rc{rc_number}"
    target_npm = npm_version(target_python, public_version)
    return current_python, target_python, current_npm, target_npm


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateError(f"Cannot read {label} {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateError(f"{label} must be a JSON object: {path}")
    return payload


def validate_aggregate_summary(
    summary_path: Path,
    evidence_inputs: list[Path],
    *,
    expected_commit: str,
) -> tuple[dict[str, Any], list[Path]]:
    contract = evidence.load_contract()
    paths = evidence.discover_reports(evidence_inputs)
    rebuilt = evidence.aggregate_reports(
        paths,
        contract=contract,
        expected_commit=expected_commit,
    )
    summary = load_json_object(summary_path, "aggregate evidence")
    evidence.expect_exact_keys(
        summary,
        {
            "schema_version",
            "status",
            "aggregated_at",
            "source_commit",
            "contract",
            "package_version",
            "platforms",
        },
        str(summary_path),
    )
    evidence.parse_verified_at(summary["aggregated_at"], f"{summary_path}: aggregated_at")
    for field in (
        "schema_version",
        "status",
        "source_commit",
        "contract",
        "package_version",
        "platforms",
    ):
        if summary[field] != rebuilt[field]:
            raise CandidateError(
                f"Aggregate evidence field {field!r} does not match the platform reports."
            )
    return summary, paths


def build_version_updates(
    root: Path,
    *,
    current_python: str,
    target_python: str,
    current_npm: str,
    target_npm: str,
) -> dict[Path, str]:
    updates: dict[Path, str] = {}
    for source in VERSION_SOURCES:
        path = root / source.path
        try:
            original = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CandidateError(f"Cannot read version source {source.path}: {exc}") from exc
        old = current_python if source.flavor == "python" else current_npm
        new = target_python if source.flavor == "python" else target_npm
        actual_count = original.count(old)
        if actual_count != source.expected_count:
            raise CandidateError(
                f"{source.path} contains {actual_count} occurrences of {old!r}; "
                f"expected {source.expected_count}."
            )
        updates[source.path] = original.replace(old, new)
    return updates


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def apply_version_updates(updates: dict[Path, str]) -> None:
    tracked_paths = set(updates) | set(GENERATED_METADATA)
    originals = {
        relative: (ROOT / relative).read_bytes()
        for relative in tracked_paths
        if (ROOT / relative).exists()
    }
    try:
        for relative, content in updates.items():
            atomic_write(ROOT / relative, content)
        subprocess.run(
            [sys.executable, "packaging/generate_release_metadata.py"],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [sys.executable, "packaging/generate_release_metadata.py", "--check"],
            cwd=ROOT,
            check=True,
        )
    except Exception:
        for relative in tracked_paths:
            path = ROOT / relative
            if relative in originals:
                path.write_bytes(originals[relative])
            elif path.exists():
                path.unlink()
        raise


def write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a release-candidate version after verified three-platform evidence."
    )
    parser.add_argument("--summary", required=True, type=Path, help="Aggregate evidence JSON.")
    parser.add_argument(
        "--evidence",
        required=True,
        nargs="+",
        type=Path,
        help="Platform evidence files or directories.",
    )
    parser.add_argument("--rc-number", type=int, default=1)
    parser.add_argument("--plan-json", type=Path, help="Write the reviewed version-change plan.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the version changes. The default is a validation-only dry run.",
    )
    args = parser.parse_args()

    if not git_is_clean():
        parser.exit(1, "release candidate rejected: the Git working tree is not clean\n")
    expected_commit = git_value("rev-parse", "HEAD")
    try:
        summary, reports = validate_aggregate_summary(
            args.summary.resolve(),
            args.evidence,
            expected_commit=expected_commit,
        )
        contract = evidence.load_contract()
        current_python, target_python, current_npm, target_npm = target_versions(
            contract, args.rc_number
        )
        updates = build_version_updates(
            ROOT,
            current_python=current_python,
            target_python=target_python,
            current_npm=current_npm,
            target_npm=target_npm,
        )
    except (CandidateError, evidence.EvidenceError) as exc:
        parser.exit(1, f"release candidate rejected: {exc}\n")

    plan = {
        "schema_version": 1,
        "status": "applied" if args.apply else "validated",
        "source_commit": expected_commit,
        "evidence": {
            "summary_sha256": evidence.sha256(args.summary.resolve()),
            "platform_report_sha256": sorted(evidence.sha256(path) for path in reports),
            "aggregated_at": summary["aggregated_at"],
        },
        "version": {
            "current_python": current_python,
            "target_python": target_python,
            "current_npm": current_npm,
            "target_npm": target_npm,
        },
        "files": sorted(path.as_posix() for path in updates),
    }

    if args.apply:
        try:
            apply_version_updates(updates)
        except (OSError, subprocess.CalledProcessError) as exc:
            parser.exit(1, f"release candidate update failed and was rolled back: {exc}\n")
    if args.plan_json:
        write_json(args.plan_json.resolve(), plan)
    action = "applied" if args.apply else "validated"
    print(f"release candidate {target_python} {action} from evidence for {expected_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
