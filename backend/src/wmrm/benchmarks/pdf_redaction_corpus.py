import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import pymupdf
from pypdf import PdfReader

from wmrm.adapters.pdf.pymupdf_redaction import redact_pdf_regions

ALLOWED_PROVENANCE = {"repository_application_export"}


class PdfRedactionCorpusError(ValueError):
    pass


def run_corpus_audit(
    manifest_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise PdfRedactionCorpusError("Unsupported PDF redaction corpus schema version.")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise PdfRedactionCorpusError("PDF redaction corpus must contain samples.")

    results = [_audit_sample(manifest_path.parent, sample) for sample in samples]
    mismatch_count = sum(len(item["mismatches"]) for item in results)
    report = {
        "schema_version": 1,
        "audit": "wmrm-pdf-redaction-producer-corpus",
        "manifest": manifest_path.name,
        "pymupdf_version": pymupdf.__version__,
        "summary": {
            "sample_count": len(results),
            "producer_count": len({item["producer"] for item in results}),
            "cleanup_pass_count": sum(not item["mismatches"] for item in results),
            "mismatch_count": mismatch_count,
            "status": "pass" if mismatch_count == 0 else "review",
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


def _audit_sample(root: Path, sample: dict[str, Any]) -> dict[str, Any]:
    sample_id = _required_text(sample, "id")
    provenance = _required_text(sample, "provenance")
    if provenance not in ALLOWED_PROVENANCE:
        raise PdfRedactionCorpusError(
            f"Unsupported provenance for {sample_id}: {provenance}"
        )
    if sample.get("review_required") is not False:
        raise PdfRedactionCorpusError(
            f"Application export {sample_id} must be manually reviewed and pinned."
        )

    source_pdf = _contained_file(root, _required_text(sample, "file"), sample_id)
    source_record = _contained_file(
        root, _required_text(sample, "source_record"), sample_id
    )
    source_record_sha = _sha256(source_record)
    expected_source_sha = _required_text(sample, "source_sha256")
    if source_record_sha != expected_source_sha:
        raise PdfRedactionCorpusError(
            f"Source SHA-256 mismatch for {source_record.name}: expected "
            f"{expected_source_sha}, got {source_record_sha}"
        )
    _required_text(sample, "permission_note")
    _required_text(sample, "producer")
    _required_text(sample, "producer_version")
    _required_text(sample, "export_note")
    expected_sha = _required_text(sample, "sha256")
    actual_sha = _sha256(source_pdf)
    if actual_sha != expected_sha:
        raise PdfRedactionCorpusError(
            f"SHA-256 mismatch for {source_pdf.name}: expected {expected_sha}, got {actual_sha}"
        )

    regions = sample.get("regions")
    if not isinstance(regions, list) or not regions:
        raise PdfRedactionCorpusError(f"Sample {sample_id} must define redaction regions.")
    target_text = _required_text(sample, "target_text")
    preserved_text = sample.get("preserved_text")
    if not isinstance(preserved_text, list) or not preserved_text or not all(
        isinstance(item, str) and item for item in preserved_text
    ):
        raise PdfRedactionCorpusError(f"Sample {sample_id} has invalid preserved_text.")

    source_reader = PdfReader(str(source_pdf), strict=True)
    source_pages = [_page_text(page) for page in source_reader.pages]
    source_text = "\n".join(source_pages)
    expected_pages = _required_int(sample, "page_count")
    mismatches: list[str] = []
    if len(source_reader.pages) != expected_pages:
        mismatches.append(
            f"source page_count: expected {expected_pages}, got {len(source_reader.pages)}"
        )
    if target_text not in source_text:
        mismatches.append(f"target text {target_text!r} is absent from source")
    missing_source_text = [item for item in preserved_text if item not in source_text]
    if missing_source_text:
        mismatches.append(f"preserved text absent from source: {missing_source_text!r}")

    changed_pages = sorted({int(item["page_number"]) for item in regions})
    with tempfile.TemporaryDirectory(prefix="wmrm-pdf-corpus-") as directory:
        output = Path(directory) / "result.pdf"
        operation = redact_pdf_regions(
            source_pdf, output, regions, license_mode="agpl"
        )
        result_reader = PdfReader(str(output), strict=True)
        result_pages = [_page_text(page) for page in result_reader.pages]
        result_text = "\n".join(result_pages)
        if target_text in result_text:
            mismatches.append(f"target text {target_text!r} remains after redaction")
        missing_result_text = [item for item in preserved_text if item not in result_text]
        if missing_result_text:
            mismatches.append(f"preserved text removed: {missing_result_text!r}")
        if len(result_reader.pages) != expected_pages:
            mismatches.append(
                f"result page_count: expected {expected_pages}, got {len(result_reader.pages)}"
            )
        if operation["changed_pages"] != changed_pages:
            mismatches.append(
                f"changed_pages: expected {changed_pages}, got {operation['changed_pages']}"
            )
        unchanged_pages = [
            index
            for index, (before, after) in enumerate(
                zip(source_pages, result_pages, strict=False), start=1
            )
            if index not in changed_pages and before != after
        ]
        if unchanged_pages:
            mismatches.append(
                f"text changed on unaffected pages: {unchanged_pages}"
            )
        output_sha = _sha256(output)

    return {
        "id": sample_id,
        "provenance": provenance,
        "producer": sample["producer"],
        "producer_version": sample["producer_version"],
        "file": source_pdf.relative_to(root).as_posix(),
        "sha256": actual_sha,
        "source_record": source_record.relative_to(root).as_posix(),
        "source_sha256": source_record_sha,
        "export_note": sample["export_note"],
        "page_count": len(source_reader.pages),
        "regions": regions,
        "changed_pages": changed_pages,
        "target_removed": target_text not in result_text,
        "preserved_text_count": len(preserved_text) - len(missing_result_text),
        "unaffected_pages_preserved": not unchanged_pages,
        "result_sha256": output_sha,
        "backend": operation["backend"],
        "backend_version": operation["backend_version"],
        "mismatches": mismatches,
    }


def _contained_file(root: Path, relative: str, sample_id: str) -> Path:
    path = (root / relative).resolve()
    if root not in path.parents or not path.is_file():
        raise PdfRedactionCorpusError(
            f"Invalid or missing corpus path for {sample_id}: {relative}"
        )
    return path


def _page_text(page: Any) -> str:
    return " ".join((page.extract_text() or "").split())


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise PdfRedactionCorpusError(f"Missing required text field: {field}")
    return value


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise PdfRedactionCorpusError(f"Missing required integer field: {field}")
    return value


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# PDF Redaction Producer Corpus",
        "",
        "Project-authored fixtures exported by real installed applications and "
        "checked through the production redaction backend.",
        "",
        f"- Status: **{summary['status']}**",
        f"- Samples: {summary['sample_count']}",
        f"- Producers: {summary['producer_count']}",
        f"- Passed: {summary['cleanup_pass_count']}",
        f"- Mismatches: {summary['mismatch_count']}",
        "",
        "| Producer | Version | Target removed | Unaffected pages preserved | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for sample in report["samples"]:
        result = "pass" if not sample["mismatches"] else "review"
        lines.append(
            f"| {sample['producer']} | {sample['producer_version']} | "
            f"{str(sample['target_removed']).lower()} | "
            f"{str(sample['unaffected_pages_preserved']).lower()} | {result} |"
        )
    lines.extend(
        [
            "",
            "Each manifest entry pins the exported PDF and source digests, source record, "
            "producer version, target region, and manual-review state.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit PDF redaction across application-exported fixtures"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_corpus_audit(
        args.manifest,
        report_json=args.report_json,
        report_markdown=args.report_md,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 1 if args.strict and report["summary"]["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
