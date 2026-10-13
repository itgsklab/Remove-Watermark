from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "packaging" / "stable-release-policy.json"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
RC_TAG_PATTERN = re.compile(r"v0\.1\.0rc([1-9][0-9]*)")
REQUIRED_PLATFORMS = ["Linux-X64", "macOS-ARM64", "Windows-X64"]


class StableReleaseError(RuntimeError):
    pass


def expect_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StableReleaseError(f"{label} must be a JSON object.")
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
        raise StableReleaseError(f"{label} has invalid fields ({'; '.join(details)}).")


def expect_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise StableReleaseError(f"{label} must be a non-empty string.")
    return value


def expect_timestamp(value: Any, label: str) -> str:
    text = expect_string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StableReleaseError(f"{label} must be an ISO 8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise StableReleaseError(f"{label} must include a timezone.")
    return text


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        return expect_object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, json.JSONDecodeError) as exc:
        raise StableReleaseError(f"Cannot read {label} {path}: {exc}") from exc


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    expect_exact_keys(
        policy,
        {
            "schema_version",
            "target_version",
            "delivery",
            "required_platforms",
            "required_release_candidates",
            "security_contract",
            "feedback_gate",
        },
        "policy",
    )
    if policy["schema_version"] != 1 or policy["target_version"] != "0.1.0":
        raise StableReleaseError("Policy must describe stable version 0.1.0 with schema 1.")

    delivery = expect_object(policy["delivery"], "policy.delivery")
    expect_exact_keys(delivery, {"interface", "native_applications"}, "policy.delivery")
    if delivery != {"interface": "web", "native_applications": False}:
        raise StableReleaseError("The first stable release must remain Web-only.")

    if policy["required_platforms"] != REQUIRED_PLATFORMS:
        raise StableReleaseError("Policy must require the exact Linux, macOS and Windows matrix.")

    candidates = policy["required_release_candidates"]
    if not isinstance(candidates, list) or len(candidates) < 2:
        raise StableReleaseError("Policy must pin at least two release candidates.")
    seen_tags: set[str] = set()
    rc_numbers: list[int] = []
    for index, raw_candidate in enumerate(candidates):
        label = f"policy.required_release_candidates[{index}]"
        candidate = expect_object(raw_candidate, label)
        expect_exact_keys(candidate, {"tag", "source_commit", "published_at", "assets"}, label)
        tag = expect_string(candidate["tag"], f"{label}.tag")
        match = RC_TAG_PATTERN.fullmatch(tag)
        if not match or tag in seen_tags:
            raise StableReleaseError(f"{label}.tag must be a unique v0.1.0 release candidate.")
        seen_tags.add(tag)
        rc_numbers.append(int(match.group(1)))
        if not COMMIT_PATTERN.fullmatch(expect_string(candidate["source_commit"], f"{label}.source_commit")):
            raise StableReleaseError(f"{label}.source_commit must be a full commit SHA.")
        expect_timestamp(candidate["published_at"], f"{label}.published_at")
        assets = expect_object(candidate["assets"], f"{label}.assets")
        version = tag.removeprefix("v")
        required_names = {
            "SHA256SUMS",
            "release-manifest.json",
            f"remove-watermark-web-{version}.tar.gz",
            f"wmrm-{version}-py3-none-any.whl",
            f"wmrm-{version}.tar.gz",
        }
        if set(assets) != required_names:
            raise StableReleaseError(f"{label}.assets must pin the five required Web release files.")
        for name, digest in assets.items():
            if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
                raise StableReleaseError(f"{label}.assets[{name!r}] must be a SHA-256 digest.")
    if rc_numbers != sorted(rc_numbers):
        raise StableReleaseError("Release candidates must be listed in increasing order.")

    security = expect_object(policy["security_contract"], "policy.security_contract")
    expected_security = {
        "vlm_enabled_by_default": False,
        "vlm_automatic_download": False,
        "vlm_manual_review_required": True,
        "model_weights_in_release": False,
        "private_planning_files_in_release": False,
    }
    if security != expected_security:
        raise StableReleaseError("Policy weakens the reviewed security and privacy contract.")

    gate = expect_object(policy["feedback_gate"], "policy.feedback_gate")
    expect_exact_keys(
        gate,
        {
            "minimum_sources",
            "blocking_severities",
            "require_reproducible_issue_triage",
            "require_clean_install",
            "require_browser_routes",
            "require_privacy_scan",
        },
        "policy.feedback_gate",
    )
    if not isinstance(gate["minimum_sources"], int) or gate["minimum_sources"] < 1:
        raise StableReleaseError("The feedback gate must require at least one real source.")
    if gate["blocking_severities"] != ["critical", "high"]:
        raise StableReleaseError("Critical and high issues must block stable release.")
    if gate["require_browser_routes"] != ["/", "/settings"]:
        raise StableReleaseError("Home and settings browser acceptance must remain required.")
    for field in (
        "require_reproducible_issue_triage",
        "require_clean_install",
        "require_privacy_scan",
    ):
        if gate[field] is not True:
            raise StableReleaseError(f"policy.feedback_gate.{field} must be true.")
    return policy


def validate_feedback(
    feedback: dict[str, Any],
    policy: dict[str, Any],
    *,
    require_approval: bool = True,
) -> dict[str, Any]:
    expect_exact_keys(
        feedback,
        {
            "schema_version",
            "target_version",
            "candidate_tag",
            "reviewed_at",
            "sources",
            "issues",
            "verification",
            "approval",
        },
        "feedback",
    )
    if feedback["schema_version"] != 1 or feedback["target_version"] != policy["target_version"]:
        raise StableReleaseError("Feedback does not target policy schema 1 and version 0.1.0.")
    latest_tag = policy["required_release_candidates"][-1]["tag"]
    if feedback["candidate_tag"] != latest_tag:
        raise StableReleaseError(f"Feedback must review the latest candidate {latest_tag}.")
    expect_timestamp(feedback["reviewed_at"], "feedback.reviewed_at")

    sources = feedback["sources"]
    minimum_sources = policy["feedback_gate"]["minimum_sources"]
    if not isinstance(sources, list) or len(sources) < minimum_sources:
        raise StableReleaseError(f"Feedback requires at least {minimum_sources} real source(s).")
    for index, raw_source in enumerate(sources):
        label = f"feedback.sources[{index}]"
        source = expect_object(raw_source, label)
        expect_exact_keys(source, {"kind", "reference", "collected_at"}, label)
        expect_string(source["kind"], f"{label}.kind")
        expect_string(source["reference"], f"{label}.reference")
        expect_timestamp(source["collected_at"], f"{label}.collected_at")

    issues = feedback["issues"]
    if not isinstance(issues, list):
        raise StableReleaseError("feedback.issues must be a list.")
    blocking = set(policy["feedback_gate"]["blocking_severities"])
    unresolved = []
    for index, raw_issue in enumerate(issues):
        label = f"feedback.issues[{index}]"
        issue = expect_object(raw_issue, label)
        expect_exact_keys(issue, {"id", "severity", "reproducible", "status"}, label)
        issue_id = expect_string(issue["id"], f"{label}.id")
        severity = expect_string(issue["severity"], f"{label}.severity")
        if severity not in {"critical", "high", "medium", "low"}:
            raise StableReleaseError(f"{label}.severity is unsupported.")
        if not isinstance(issue["reproducible"], bool):
            raise StableReleaseError(f"{label}.reproducible must be boolean.")
        if issue["status"] not in {"open", "closed", "deferred"}:
            raise StableReleaseError(f"{label}.status is unsupported.")
        if issue["reproducible"] and severity in blocking and issue["status"] != "closed":
            unresolved.append(issue_id)
    if unresolved:
        raise StableReleaseError("Unresolved reproducible blocking issues: " + ", ".join(unresolved))

    verification = expect_object(feedback["verification"], "feedback.verification")
    expect_exact_keys(
        verification,
        {
            "clean_install",
            "browser_routes",
            "privacy_scan",
            "vlm_enabled_by_default",
            "vlm_automatic_download",
            "vlm_manual_review_required",
        },
        "feedback.verification",
    )
    if verification["clean_install"] is not True or verification["privacy_scan"] is not True:
        raise StableReleaseError("Clean install and privacy scan must pass.")
    required_routes = set(policy["feedback_gate"]["require_browser_routes"])
    routes = verification["browser_routes"]
    if not isinstance(routes, list) or not required_routes.issubset(routes):
        raise StableReleaseError("Browser acceptance does not cover all required routes.")
    expected_vlm = {
        "vlm_enabled_by_default": False,
        "vlm_automatic_download": False,
        "vlm_manual_review_required": True,
    }
    if {key: verification[key] for key in expected_vlm} != expected_vlm:
        raise StableReleaseError("Feedback weakens the VLM opt-in contract.")

    approval = expect_object(feedback["approval"], "feedback.approval")
    expect_exact_keys(approval, {"approved", "reviewer", "approved_at"}, "feedback.approval")
    if not isinstance(approval["approved"], bool):
        raise StableReleaseError("feedback.approval.approved must be boolean.")
    if approval["approved"]:
        expect_string(approval["reviewer"], "feedback.approval.reviewer")
        expect_timestamp(approval["approved_at"], "feedback.approval.approved_at")
        status = "ready"
    elif require_approval:
        raise StableReleaseError("Stable release has not been explicitly approved.")
    else:
        if approval["reviewer"] != "" or approval["approved_at"] != "":
            raise StableReleaseError("Pending approval must not name a reviewer or approval time.")
        status = "acceptance-passed-approval-pending"
    return {
        "schema_version": 1,
        "status": status,
        "target_version": policy["target_version"],
        "candidate_tag": latest_tag,
        "feedback_sources": len(sources),
        "issues_reviewed": len(issues),
        "blocking_issues": [],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the v0.1.0 stable-release exit gate.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--feedback", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    try:
        policy = validate_policy(load_json(args.policy.resolve(), "policy"))
        if args.feedback:
            result = validate_feedback(
                load_json(args.feedback.resolve(), "feedback"),
                policy,
                require_approval=args.require_ready,
            )
        elif args.require_ready:
            raise StableReleaseError("--require-ready needs a completed --feedback record.")
        else:
            result = {
                "schema_version": 1,
                "status": "policy-valid-feedback-pending",
                "target_version": policy["target_version"],
                "release_candidates": [
                    candidate["tag"] for candidate in policy["required_release_candidates"]
                ],
            }
    except StableReleaseError as exc:
        parser.exit(1, f"stable release rejected: {exc}\n")
    if args.output_json:
        write_json(args.output_json.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
