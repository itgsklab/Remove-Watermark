import argparse
import hashlib
import json
import tempfile
from io import BytesIO
from pathlib import Path

import pypdf
from pypdf import PdfReader

from wmrm.adapters.pdf.codecv import CodeCvCandidate, CodeCvPdfInspector
from wmrm.adapters.pdf.codecv_editor import CodeCvEditError, remove_codecv_candidates

ALLOWED_PROVENANCE = {
    "repository_generated",
    "private_export",
    "redistributable_export",
}


class CodeCvCorpusError(ValueError):
    pass


def run_corpus_audit(
    manifest_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
    require_real: bool = False,
) -> dict:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise CodeCvCorpusError("Unsupported CodeCV corpus manifest schema version.")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise CodeCvCorpusError("CodeCV corpus manifest must contain samples.")

    root = manifest_path.parent
    inspector = CodeCvPdfInspector(max_pages=1000, max_content_bytes=100_000_000)
    results = [_audit_sample(root, sample, inspector) for sample in samples]
    real_count = sum(item["provenance"] != "repository_generated" for item in results)
    if require_real and real_count == 0:
        raise CodeCvCorpusError(
            "This audit requires at least one private or redistributable real export."
        )

    mismatches = sum(len(item["mismatches"]) for item in results)
    cleanup_count = sum(item["cleanup"]["attempted"] for item in results)
    cleanup_passes = sum(item["cleanup"]["passed"] for item in results)
    if mismatches:
        status = "review"
    elif real_count:
        status = "pass"
    else:
        status = "generated_only"
    report = {
        "schema_version": 1,
        "audit": "wmrm-codecv-export-corpus",
        "manifest": manifest_path.name,
        "pypdf_version": pypdf.__version__,
        "summary": {
            "sample_count": len(results),
            "generated_count": len(results) - real_count,
            "real_export_count": real_count,
            "matched_source_count": sum(
                item["actual"]["match_status"] == "matched" for item in results
            ),
            "cleanup_attempt_count": cleanup_count,
            "cleanup_pass_count": cleanup_passes,
            "mismatch_count": mismatches,
            "status": status,
        },
        "samples": results,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_markdown.write_text(_markdown(report), encoding="utf-8")
    return report


def _audit_sample(
    root: Path, sample: dict, inspector: CodeCvPdfInspector
) -> dict:
    sample_id = _required_text(sample, "id")
    provenance = _required_text(sample, "provenance")
    if provenance not in ALLOWED_PROVENANCE:
        raise CodeCvCorpusError(f"Unsupported provenance for {sample_id}: {provenance}")
    if provenance != "repository_generated" and sample.get("review_required") is not False:
        raise CodeCvCorpusError(
            f"Real export {sample_id} must set review_required to false after manual review."
        )
    if provenance != "repository_generated":
        _required_text(sample, "source_record")
        _required_text(sample, "permission_note")
    relative_path = Path(_required_text(sample, "file"))
    source_path = (root / relative_path).resolve()
    if root not in source_path.parents:
        raise CodeCvCorpusError(f"Sample path leaves manifest directory: {relative_path}")
    if not source_path.is_file():
        raise CodeCvCorpusError(f"Missing CodeCV corpus sample: {relative_path}")
    source_bytes = source_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    expected_sha256 = _required_text(sample, "sha256")
    if source_sha256 != expected_sha256:
        raise CodeCvCorpusError(
            f"SHA-256 mismatch for {relative_path}: expected {expected_sha256}, "
            f"got {source_sha256}"
        )

    reader = PdfReader(BytesIO(source_bytes), strict=False)
    source_text_sha256 = _text_sha256(reader)
    expected = sample.get("expected")
    if not isinstance(expected, dict):
        raise CodeCvCorpusError(f"Missing expected results for {sample_id}")
    inspection = inspector.inspect(source_path, source_sha256)
    candidates = list(inspection.candidates)
    actual = {
        "page_count": len(reader.pages),
        "text_sha256": source_text_sha256,
        "match_status": inspection.match_status,
        "candidate_count": len(candidates),
        "confirmed_count": sum(item.classification == "confirmed" for item in candidates),
        "ambiguous_count": sum(item.classification == "ambiguous" for item in candidates),
        "candidate_pages": sorted({item.page_number for item in candidates}),
        "resource_names": sorted(
            {item.resource_name for item in candidates if item.resource_name}
        ),
    }
    pinned = {
        "page_count": _required_int(sample, "page_count"),
        "text_sha256": _required_text(sample, "text_sha256"),
        "match_status": _required_text(expected, "match_status"),
        "candidate_count": _required_int(expected, "candidate_count"),
        "confirmed_count": _required_int(expected, "confirmed_count"),
        "candidate_pages": expected.get("candidate_pages"),
    }
    if not isinstance(pinned["candidate_pages"], list):
        raise CodeCvCorpusError(f"Invalid candidate_pages for {sample_id}")
    mismatches = [
        f"{field}: expected {wanted!r}, got {actual[field]!r}"
        for field, wanted in pinned.items()
        if actual[field] != wanted
    ]

    cleanup = {
        "attempted": False,
        "passed": False,
        "removed_count": 0,
        "clean_match_status": None,
        "result_text_sha256": None,
        "result_page_count": None,
        "error": None,
    }
    clean_expected = expected.get("clean_match_status")
    confirmed = [item for item in candidates if item.classification == "confirmed"]
    if clean_expected is not None:
        cleanup["attempted"] = True
        if not confirmed:
            cleanup["error"] = "No confirmed candidates were available for cleanup."
            mismatches.append(cleanup["error"])
        else:
            try:
                with tempfile.TemporaryDirectory(prefix="wmrm-codecv-audit-") as temporary:
                    output_path = Path(temporary) / "cleaned.pdf"
                    edit_result = remove_codecv_candidates(
                        source_path,
                        output_path,
                        [_candidate_payload(item) for item in confirmed],
                    )
                    output_sha256 = hashlib.sha256(output_path.read_bytes()).hexdigest()
                    cleaned = inspector.inspect(output_path, output_sha256)
                    result_reader = PdfReader(str(output_path), strict=True)
                    cleanup.update(
                        {
                            "removed_count": edit_result["removed_count"],
                            "clean_match_status": cleaned.match_status,
                            "result_text_sha256": _text_sha256(result_reader),
                            "result_page_count": len(result_reader.pages),
                        }
                    )
            except (CodeCvEditError, OSError, ValueError) as error:
                cleanup["error"] = str(error)
                mismatches.append(f"cleanup failed: {error}")
            else:
                cleanup_checks = {
                    "clean_match_status": clean_expected,
                    "result_text_sha256": source_text_sha256,
                    "result_page_count": len(reader.pages),
                    "removed_count": len(confirmed),
                }
                cleanup_mismatches = [
                    f"cleanup {field}: expected {wanted!r}, got {cleanup[field]!r}"
                    for field, wanted in cleanup_checks.items()
                    if cleanup[field] != wanted
                ]
                mismatches.extend(cleanup_mismatches)
                cleanup["passed"] = not cleanup_mismatches

    return {
        "id": sample_id,
        "provenance": provenance,
        "template_version": _required_text(sample, "template_version"),
        "file": relative_path.as_posix(),
        "sha256": source_sha256,
        "source_record": sample.get("source_record"),
        "permission_note": sample.get("permission_note"),
        "expected": expected,
        "actual": actual,
        "cleanup": cleanup,
        "mismatches": mismatches,
    }


def _candidate_payload(candidate: CodeCvCandidate) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "source_locator": {
            "page_numbers": [candidate.page_number],
            "resource_name": candidate.resource_name,
            "object_number": candidate.object_number,
            "generation_number": candidate.generation_number,
            "operation_index": candidate.operation_index,
        },
    }


def _text_sha256(reader: PdfReader) -> str:
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _required_text(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CodeCvCorpusError(f"Missing required text field: {field}")
    return value


def _required_int(payload: dict, field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CodeCvCorpusError(f"Missing or invalid integer field: {field}")
    return value


def _markdown(report: dict) -> str:
    summary = report["summary"]
    rows = [
        "| Sample | Provenance | Template | Pages | Source | Candidates | Cleanup | Mismatches |",
        "|---|---|---|---:|---|---:|---|---:|",
    ]
    for sample in report["samples"]:
        cleanup = sample["cleanup"]
        cleanup_status = (
            "pass" if cleanup["passed"] else "failed" if cleanup["attempted"] else "n/a"
        )
        rows.append(
            f"| {sample['id']} | {sample['provenance']} | {sample['template_version']} | "
            f"{sample['actual']['page_count']} | {sample['actual']['match_status']} | "
            f"{sample['actual']['candidate_count']} | {cleanup_status} | "
            f"{len(sample['mismatches'])} |"
        )
    details = []
    for sample in report["samples"]:
        details.extend(
            [
                f"### {sample['id']}",
                "",
                f"- File: `{sample['file']}` (`{sample['sha256']}`)",
                f"- Text SHA-256: `{sample['actual']['text_sha256']}`",
                f"- Candidate pages: `{sample['actual']['candidate_pages']}`",
                f"- Pattern resources: `{sample['actual']['resource_names']}`",
                f"- Cleanup removed: `{sample['cleanup']['removed_count']}`",
                (
                    "- Mismatches: none"
                    if not sample["mismatches"]
                    else f"- Mismatches: `{sample['mismatches']}`"
                ),
                "",
            ]
        )
    return "\n".join(
        [
            "# CodeCV export corpus audit",
            "",
            f"Status: **{summary['status']}** · Samples: {summary['sample_count']} · "
            f"Real exports: {summary['real_export_count']} · "
            f"Cleanup: {summary['cleanup_pass_count']}/{summary['cleanup_attempt_count']} · "
            f"Mismatches: {summary['mismatch_count']}",
            "",
            (
                "`generated_only` means the audit harness is working, but no real CodeCV "
                "export has been supplied. It must not be treated as template compatibility "
                "evidence."
            ),
            "",
            *rows,
            "",
            "## Sample details",
            "",
            *details,
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a CodeCV PDF export corpus.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-real", action="store_true")
    args = parser.parse_args()
    report = run_corpus_audit(
        args.manifest,
        report_json=args.report_json,
        report_markdown=args.report_md,
        require_real=args.require_real,
    )
    if args.strict and report["summary"]["mismatch_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
