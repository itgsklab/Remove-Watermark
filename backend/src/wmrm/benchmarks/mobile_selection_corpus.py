import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PIL import Image

from wmrm.adapters.images.selection_risk import (
    LARGE_SELECTION_THRESHOLD,
    LOW_CONTRAST_THRESHOLD,
    ImageSelectionRiskInspector,
)


class MobileSelectionCorpusError(ValueError):
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
        raise MobileSelectionCorpusError("Unsupported mobile selection corpus schema.")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise MobileSelectionCorpusError("Mobile selection corpus must contain samples.")

    inspector = ImageSelectionRiskInspector()
    results = [_audit_sample(manifest_path.parent, sample, inspector) for sample in samples]
    mismatch_count = sum(len(item["mismatches"]) for item in results)
    report = {
        "schema_version": 1,
        "audit": "wmrm-mobile-selection-real-background-corpus",
        "manifest": manifest_path.name,
        "thresholds": {
            "low_contrast": LOW_CONTRAST_THRESHOLD,
            "large_selection": LARGE_SELECTION_THRESHOLD,
        },
        "summary": {
            "sample_count": len(results),
            "low_contrast_count": sum(item["actual_low_contrast"] for item in results),
            "large_selection_count": sum(
                item["actual_large_selection"] for item in results
            ),
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


def _audit_sample(
    root: Path,
    sample: dict[str, Any],
    inspector: ImageSelectionRiskInspector,
) -> dict[str, Any]:
    sample_id = _required_text(sample, "id")
    if sample.get("review_required") is not False:
        raise MobileSelectionCorpusError(
            f"Sample {sample_id} must be manually reviewed before audit."
        )
    image_path = _contained_file(root, _required_text(sample, "file"), root)
    source_path = _contained_file(
        root, _required_text(sample, "source_file"), root.parent
    )
    _verify_sha(image_path, _required_text(sample, "sha256"))
    _verify_sha(source_path, _required_text(sample, "source_sha256"))
    for field in (
        "source_record",
        "usage_terms_url",
        "attribution",
        "provenance_note",
        "transformation",
    ):
        _required_text(sample, field)

    with Image.open(image_path) as image:
        width, height = image.size
    if width != _required_int(sample, "width") or height != _required_int(
        sample, "height"
    ):
        raise MobileSelectionCorpusError(f"Dimension mismatch for {sample_id}.")
    region = sample.get("region")
    if not isinstance(region, dict):
        raise MobileSelectionCorpusError(f"Missing region for {sample_id}.")
    coordinates = [_required_number(region, key) for key in ("x0", "y0", "x1", "y1")]
    x0, y0, x1, y1 = coordinates
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise MobileSelectionCorpusError(f"Out-of-bounds region for {sample_id}.")

    assessment = inspector.inspect(image_path, [SimpleNamespace(**region)])[0]
    coverage = (int(x1) - int(x0)) * (int(y1) - int(y0)) / (width * height)
    expected_low = _required_bool(sample, "expected_low_contrast")
    expected_large = _required_bool(sample, "expected_large_selection")
    actual_large = coverage >= LARGE_SELECTION_THRESHOLD
    mismatches = []
    if assessment.low_contrast != expected_low:
        mismatches.append(
            f"low_contrast: expected {expected_low}, got {assessment.low_contrast}"
        )
    if actual_large != expected_large:
        mismatches.append(
            f"large_selection: expected {expected_large}, got {actual_large}"
        )
    return {
        "id": sample_id,
        "file": image_path.relative_to(root).as_posix(),
        "sha256": _sha256(image_path),
        "source_file": source_path.relative_to(root.parent).as_posix(),
        "source_sha256": _sha256(source_path),
        "source_record": sample["source_record"],
        "usage_terms_url": sample["usage_terms_url"],
        "attribution": sample["attribution"],
        "provenance_note": sample["provenance_note"],
        "transformation": sample["transformation"],
        "coverage_ratio": round(coverage, 4),
        "mean_luma_delta": assessment.mean_luma_delta,
        "expected_low_contrast": expected_low,
        "actual_low_contrast": assessment.low_contrast,
        "expected_large_selection": expected_large,
        "actual_large_selection": actual_large,
        "mismatches": mismatches,
    }


def _contained_file(root: Path, relative: str, boundary: Path) -> Path:
    path = (root / relative).resolve()
    if boundary != path and boundary not in path.parents:
        raise MobileSelectionCorpusError(f"Corpus path leaves allowed root: {relative}")
    if not path.is_file():
        raise MobileSelectionCorpusError(f"Missing corpus file: {relative}")
    return path


def _verify_sha(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise MobileSelectionCorpusError(
            f"SHA-256 mismatch for {path.name}: expected {expected}, got {actual}"
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MobileSelectionCorpusError(f"Missing required text field: {field}")
    return value


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise MobileSelectionCorpusError(f"Missing required integer field: {field}")
    return value


def _required_bool(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise MobileSelectionCorpusError(f"Missing required boolean field: {field}")
    return value


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise MobileSelectionCorpusError(f"Missing required numeric field: {field}")
    return float(value)


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = [
        "| Sample | Coverage | Luma delta | Low contrast | Large | Result |",
        "|---|---:|---:|---|---|---|",
    ]
    for sample in report["samples"]:
        rows.append(
            f"| {sample['id']} | {sample['coverage_ratio'] * 100:.2f}% | "
            f"{sample['mean_luma_delta'] * 100:.2f}% | "
            f"{str(sample['actual_low_contrast']).lower()} | "
            f"{str(sample['actual_large_selection']).lower()} | "
            f"{'pass' if not sample['mismatches'] else 'review'} |"
        )
    sources = []
    for sample in report["samples"]:
        sources.extend(
            [
                f"### {sample['id']}",
                "",
                f"- Attribution: {sample['attribution']}",
                f"- Provenance: {sample['provenance_note']}",
                f"- Transformation: {sample['transformation']}",
                f"- [Source record]({sample['source_record']}) · "
                f"[usage terms]({sample['usage_terms_url']})",
                "",
            ]
        )
    return "\n".join(
        [
            "# Mobile selection real-background corpus",
            "",
            (
                "The underlying pixels come from provenance-recorded NASA photographs. "
                "Portrait crops and watermark overlays are generated by this repository."
            ),
            "",
            f"Status: **{summary['status']}** · Samples: {summary['sample_count']} · "
            f"Mismatches: {summary['mismatch_count']}",
            "",
            *rows,
            "",
            "Every entry pins both source and derived SHA-256 digests, transformation, "
            "source record, attribution and manual-review state.",
            "",
            "## Provenance",
            "",
            *sources,
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit real-background mobile selections.")
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
