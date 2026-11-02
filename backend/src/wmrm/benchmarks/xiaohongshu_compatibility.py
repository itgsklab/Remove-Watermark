from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from wmrm.adapters.xiaohongshu.links import PARSER_RULE_VERSION, extract_metadata


class XiaohongshuCompatibilityError(ValueError):
    pass


def run_compatibility_audit(
    manifest_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("schema_version") != 1:
        raise XiaohongshuCompatibilityError("Unsupported compatibility manifest schema.")
    if manifest.get("provenance") != "repository_generated":
        raise XiaohongshuCompatibilityError("Compatibility fixtures must be repository generated.")
    privacy = manifest.get("privacy")
    if privacy != {
        "contains_user_content": False,
        "contains_live_share_links": False,
        "network_access_required": False,
    }:
        raise XiaohongshuCompatibilityError("Compatibility privacy declaration is incomplete.")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise XiaohongshuCompatibilityError("Compatibility manifest must contain cases.")

    results = [_audit_case(case) for case in cases]
    mismatch_count = sum(len(case["mismatches"]) for case in results)
    report = {
        "schema_version": 1,
        "audit": "wmrm-xiaohongshu-parser-compatibility",
        "parser_version": PARSER_RULE_VERSION,
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "privacy": privacy,
        "summary": {
            "case_count": len(results),
            "matched_expectation_count": sum(not case["mismatches"] for case in results),
            "mismatch_count": mismatch_count,
            "status": "pass" if mismatch_count == 0 else "review",
        },
        "cases": results,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_markdown.write_text(_markdown(report), encoding="utf-8")
    return report


def _audit_case(case: object) -> dict[str, Any]:
    if not isinstance(case, dict):
        raise XiaohongshuCompatibilityError("Each compatibility case must be an object.")
    case_id = _required_text(case, "id")
    note_id = _required_text(case, "synthetic_note_id")
    html = _required_text(case, "html")
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise XiaohongshuCompatibilityError(f"Missing expected result for {case_id}.")
    expected_codes = expected.get("diagnostic_codes")
    if not isinstance(expected_codes, list) or any(
        not isinstance(code, str) for code in expected_codes
    ):
        raise XiaohongshuCompatibilityError(f"Invalid diagnostic codes for {case_id}.")
    expected_result = {
        "page_structure_status": _required_text(expected, "page_structure_status"),
        "candidate_count": _required_int(expected, "candidate_count"),
        "diagnostic_codes": expected_codes,
    }
    metadata = extract_metadata(
        html.encode("utf-8"),
        f"https://www.xiaohongshu.com/explore/{note_id}",
    )
    actual = {
        "page_structure_status": metadata.page_structure_status,
        "candidate_count": len(metadata.media_candidates),
        "diagnostic_codes": list(metadata.diagnostic_codes),
    }
    mismatches = [
        f"{field}: expected {wanted!r}, got {actual[field]!r}"
        for field, wanted in expected_result.items()
        if actual[field] != wanted
    ]
    return {
        "id": case_id,
        "expected": expected_result,
        "actual": actual,
        "mismatches": mismatches,
    }


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise XiaohongshuCompatibilityError(f"Missing required text field: {field}")
    return value


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise XiaohongshuCompatibilityError(f"Missing or invalid integer field: {field}")
    return value


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = [
        "| Case | Structure | Candidates | Diagnostics | Result |",
        "|---|---|---:|---|---|",
    ]
    for case in report["cases"]:
        diagnostics = ", ".join(case["actual"]["diagnostic_codes"]) or "none"
        result = "pass" if not case["mismatches"] else "review"
        rows.append(
            f"| {case['id']} | {case['actual']['page_structure_status']} | "
            f"{case['actual']['candidate_count']} | {diagnostics} | {result} |"
        )
    return "\n".join(
        [
            "# Xiaohongshu parser compatibility audit",
            "",
            "This offline audit uses repository-generated HTML only. It performs no network "
            "access",
            "and records no share links, page text, media URLs or user content in the report.",
            "",
            f"- Parser version: `{report['parser_version']}`",
            f"- Cases: `{summary['case_count']}`",
            f"- Matched expectations: `{summary['matched_expectation_count']}`",
            f"- Mismatches: `{summary['mismatch_count']}`",
            f"- Status: `{summary['status']}`",
            "",
            *rows,
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit generated Xiaohongshu parser fixtures.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    try:
        report = run_compatibility_audit(
            args.manifest,
            report_json=args.report_json,
            report_markdown=args.report_md,
        )
    except (OSError, json.JSONDecodeError, XiaohongshuCompatibilityError) as error:
        parser.exit(1, f"Xiaohongshu compatibility audit rejected: {error}\n")
    if args.strict and report["summary"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
