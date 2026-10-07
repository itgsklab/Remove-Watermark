from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLI_CONTRACT = ROOT / "packaging" / "cli-contract-v1.json"
REQUIRED_SYSTEMS = ("Darwin", "Linux", "Windows")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


class EvidenceError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def expect_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object.")
    return value


def expect_exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise EvidenceError(f"{label} has invalid fields ({'; '.join(details)}).")


def expect_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"{label} must be a non-empty string.")
    return value


def expect_sha256(value: Any, label: str) -> str:
    text = expect_string(value, label)
    if not SHA256_PATTERN.fullmatch(text):
        raise EvidenceError(f"{label} must be a lowercase SHA-256 digest.")
    return text


def load_contract() -> dict[str, Any]:
    contract = expect_object(json.loads(CLI_CONTRACT.read_text(encoding="utf-8")), "contract")
    if contract.get("contract_version") != 1:
        raise EvidenceError("Unsupported CLI contract version.")
    return contract


def discover_reports(inputs: list[Path]) -> list[Path]:
    reports: list[Path] = []
    for supplied in inputs:
        path = supplied.resolve()
        if path.is_file():
            reports.append(path)
        elif path.is_dir():
            reports.extend(sorted(path.rglob("release-readiness.json")))
        else:
            raise EvidenceError(f"Evidence input does not exist: {supplied}")
    unique = list(dict.fromkeys(reports))
    if not unique:
        raise EvidenceError("No release-readiness.json evidence reports were found.")
    return unique


def parse_verified_at(value: Any, label: str) -> str:
    text = expect_string(value, label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise EvidenceError(f"{label} must be an ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise EvidenceError(f"{label} must include a timezone.")
    return text


def validate_report(
    path: Path,
    *,
    contract: dict[str, Any],
    expected_commit: str,
) -> dict[str, Any]:
    try:
        report = expect_object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"Cannot read evidence report {path}: {exc}") from exc

    expect_exact_keys(
        report,
        {
            "schema_version",
            "status",
            "verified_at",
            "source_commit",
            "source_dirty",
            "contract",
            "package",
            "runtime",
            "verified",
        },
        str(path),
    )
    if report["schema_version"] != 1:
        raise EvidenceError(f"{path} uses an unsupported evidence schema.")
    if report["status"] != "passed":
        raise EvidenceError(f"{path} does not record a passing verification.")
    parse_verified_at(report["verified_at"], f"{path}: verified_at")
    if report["source_commit"] != expected_commit:
        raise EvidenceError(
            f"{path} was generated for {report['source_commit']!r}, expected {expected_commit}."
        )
    if report["source_dirty"] is not False:
        raise EvidenceError(f"{path} was generated from a dirty source tree.")

    contract_evidence = expect_object(report["contract"], f"{path}: contract")
    expect_exact_keys(
        contract_evidence,
        {"version", "sha256", "target_public_version"},
        f"{path}: contract",
    )
    expected_contract = {
        "version": contract["contract_version"],
        "sha256": sha256(CLI_CONTRACT),
        "target_public_version": contract["target_public_version"],
    }
    expect_sha256(contract_evidence["sha256"], f"{path}: contract.sha256")
    if contract_evidence != expected_contract:
        raise EvidenceError(f"{path} does not match the committed CLI contract.")

    package = expect_object(report["package"], f"{path}: package")
    expect_exact_keys(package, {"version", "wheel", "wheel_sha256"}, f"{path}: package")
    if package["version"] != contract["development_version"]:
        raise EvidenceError(f"{path} has an unexpected package version.")
    wheel = expect_string(package["wheel"], f"{path}: package.wheel")
    if wheel != f"wmrm-{contract['development_version']}-py3-none-any.whl":
        raise EvidenceError(f"{path} has an unexpected wheel filename.")
    expect_sha256(package["wheel_sha256"], f"{path}: package.wheel_sha256")

    runtime = expect_object(report["runtime"], f"{path}: runtime")
    expect_exact_keys(
        runtime,
        {"system", "release", "architecture", "python"},
        f"{path}: runtime",
    )
    for field in ("system", "release", "architecture", "python"):
        expect_string(runtime[field], f"{path}: runtime.{field}")
    if runtime["system"] not in REQUIRED_SYSTEMS:
        raise EvidenceError(f"{path} records unsupported system {runtime['system']!r}.")
    if runtime["python"] != "3.12.10":
        raise EvidenceError(f"{path} was not verified with Python 3.12.10.")

    verified = expect_object(report["verified"], f"{path}: verified")
    expect_exact_keys(
        verified,
        {"commands", "exit_codes", "plan_schemas"},
        f"{path}: verified",
    )
    if verified["commands"] != sorted(contract["commands"]):
        raise EvidenceError(f"{path} does not cover every v1 CLI command.")
    if verified["exit_codes"] != sorted(contract["exit_codes"].values()):
        raise EvidenceError(f"{path} does not cover every v1 exit code.")
    if verified["plan_schemas"] != contract["plan_schemas"]:
        raise EvidenceError(f"{path} does not cover every v1 plan schema.")
    return report


def aggregate_reports(
    paths: list[Path],
    *,
    contract: dict[str, Any],
    expected_commit: str,
) -> dict[str, Any]:
    by_system: dict[str, tuple[Path, dict[str, Any]]] = {}
    for path in paths:
        report = validate_report(path, contract=contract, expected_commit=expected_commit)
        system = report["runtime"]["system"]
        if system in by_system:
            previous = by_system[system][0]
            raise EvidenceError(f"Duplicate {system} evidence: {previous} and {path}.")
        by_system[system] = (path, report)

    missing = sorted(set(REQUIRED_SYSTEMS) - set(by_system))
    if missing:
        raise EvidenceError("Missing required platform evidence: " + ", ".join(missing) + ".")
    if len(by_system) != len(REQUIRED_SYSTEMS):
        raise EvidenceError("The release gate requires exactly one report per platform.")

    platforms = {}
    for system in REQUIRED_SYSTEMS:
        path, report = by_system[system]
        platforms[system] = {
            "architecture": report["runtime"]["architecture"],
            "release": report["runtime"]["release"],
            "python": report["runtime"]["python"],
            "verified_at": report["verified_at"],
            "wheel": report["package"]["wheel"],
            "wheel_sha256": report["package"]["wheel_sha256"],
            "evidence_sha256": sha256(path),
        }

    return {
        "schema_version": 1,
        "status": "passed",
        "aggregated_at": datetime.now(UTC).isoformat(),
        "source_commit": expected_commit,
        "contract": {
            "version": contract["contract_version"],
            "sha256": sha256(CLI_CONTRACT),
            "target_public_version": contract["target_public_version"],
        },
        "package_version": contract["development_version"],
        "platforms": platforms,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Require matching Linux, macOS and Windows release-readiness evidence."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Evidence files or directories containing release-readiness.json files.",
    )
    parser.add_argument(
        "--expected-commit",
        help="Full 40-character Git commit. Defaults to GITHUB_SHA or the current HEAD.",
    )
    parser.add_argument("--output-json", type=Path, help="Write the passing aggregate report.")
    args = parser.parse_args()

    expected_commit = args.expected_commit or os.environ.get("GITHUB_SHA") or git_value(
        "rev-parse", "HEAD"
    )
    if not COMMIT_PATTERN.fullmatch(expected_commit):
        parser.error("--expected-commit must be a lowercase 40-character Git commit")

    try:
        contract = load_contract()
        reports = discover_reports(args.inputs)
        aggregate = aggregate_reports(
            reports,
            contract=contract,
            expected_commit=expected_commit,
        )
    except EvidenceError as exc:
        parser.exit(1, f"release evidence rejected: {exc}\n")

    if args.output_json:
        write_json(args.output_json.resolve(), aggregate)
    systems = ", ".join(aggregate["platforms"])
    print(f"release evidence verified for {systems}: {expected_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
