import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
import PIL
from PIL import Image

from wmrm.adapters.images.complexity import (
    EDGE_HIGH_THRESHOLD,
    EDGE_REVIEW_THRESHOLD,
    MAX_SAMPLE_DIMENSION,
    PERIODICITY_HIGH_THRESHOLD,
    PERIODICITY_MIN_TEXTURE,
    STRUCTURE_HIGH_THRESHOLD,
    STRUCTURE_SCORE_NORMALIZER,
    TEXTURE_REVIEW_THRESHOLD,
    TEXTURE_SCORE_NORMALIZER,
    ImageComplexityInspector,
    RiskLevel,
)

SampleKind = Literal["photo", "screenshot"]


@dataclass(frozen=True, slots=True)
class CalibrationRegion:
    id: str
    label: str
    expected: RiskLevel
    x0: float
    y0: float
    x1: float
    y1: float


class CalibrationError(ValueError):
    pass


def run_calibration(
    manifest_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
) -> dict:
    manifest_path = manifest_path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise CalibrationError("Unsupported calibration manifest schema version.")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise CalibrationError("Calibration manifest must contain at least one sample.")
    labeling_protocol = _required_text(payload, "labeling_protocol")

    inspector = ImageComplexityInspector()
    results: list[dict] = []
    sample_summaries: list[dict] = []
    region_ids: set[str] = set()
    manifest_root = manifest_path.parent
    for sample in samples:
        sample_id = _required_text(sample, "id")
        kind = _required_text(sample, "kind")
        if kind not in {"photo", "screenshot"}:
            raise CalibrationError(f"Unsupported sample kind for {sample_id}: {kind}")
        relative_path = Path(_required_text(sample, "file"))
        image_path = (manifest_root / relative_path).resolve()
        if manifest_root not in image_path.parents:
            raise CalibrationError(f"Sample path leaves manifest directory: {relative_path}")
        if not image_path.is_file():
            raise CalibrationError(f"Missing calibration sample: {relative_path}")
        expected_sha256 = _required_text(sample, "sha256")
        actual_sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if actual_sha256 != expected_sha256:
            raise CalibrationError(
                f"SHA-256 mismatch for {relative_path}: expected {expected_sha256}, "
                f"got {actual_sha256}"
            )

        with Image.open(image_path) as image:
            width, height = image.size
        regions = [_parse_region(item, sample_id, width, height) for item in sample["regions"]]
        for region in regions:
            identity = f"{sample_id}:{region.id}"
            if identity in region_ids:
                raise CalibrationError(f"Duplicate calibration region: {identity}")
            region_ids.add(identity)
        assessments = inspector.inspect(image_path, regions)
        sample_results = []
        for region_payload, region, assessment in zip(
            sample["regions"], regions, assessments, strict=True
        ):
            item = {
                "sample_id": sample_id,
                "kind": kind,
                "region_id": region.id,
                "label": region.label,
                "label_rationale": _required_text(region_payload, "label_rationale"),
                "expected": region.expected,
                "actual": assessment.risk,
                "matched": region.expected == assessment.risk,
                "scores": {
                    "texture": assessment.texture_score,
                    "edge_density": assessment.edge_density,
                    "periodicity": assessment.periodicity_score,
                    "structure": assessment.structure_score,
                },
                "reasons": assessment.reasons,
            }
            results.append(item)
            sample_results.append(item)
        sample_summaries.append(
            {
                "id": sample_id,
                "kind": kind,
                "file": relative_path.as_posix(),
                "sha256": actual_sha256,
                "width": width,
                "height": height,
                "source_url": sample.get("source_url"),
                "source_record": sample.get("source_record"),
                "usage_terms_url": sample.get("usage_terms_url"),
                "attribution": _required_text(sample, "attribution"),
                "provenance_note": _required_text(sample, "provenance_note"),
                "region_count": len(sample_results),
                "matched_regions": sum(item["matched"] for item in sample_results),
            }
        )

    expected_counts = {
        level: sum(item["expected"] == level for item in results)
        for level in ("low", "review", "high")
    }
    actual_counts = {
        level: sum(item["actual"] == level for item in results)
        for level in ("low", "review", "high")
    }
    matches = sum(item["matched"] for item in results)
    report = {
        "schema_version": 1,
        "calibration": "wmrm-image-complexity-real-sample-audit",
        "manifest": manifest_path.name,
        "labeling_protocol": labeling_protocol,
        "versions": {
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "pillow": PIL.__version__,
        },
        "thresholds": {
            "max_sample_dimension": MAX_SAMPLE_DIMENSION,
            "texture_score_normalizer": TEXTURE_SCORE_NORMALIZER,
            "structure_score_normalizer": STRUCTURE_SCORE_NORMALIZER,
            "periodicity_high": PERIODICITY_HIGH_THRESHOLD,
            "periodicity_min_texture": PERIODICITY_MIN_TEXTURE,
            "structure_high": STRUCTURE_HIGH_THRESHOLD,
            "edge_high": EDGE_HIGH_THRESHOLD,
            "texture_review": TEXTURE_REVIEW_THRESHOLD,
            "edge_review": EDGE_REVIEW_THRESHOLD,
        },
        "summary": {
            "sample_count": len(sample_summaries),
            "photo_count": sum(item["kind"] == "photo" for item in sample_summaries),
            "screenshot_count": sum(
                item["kind"] == "screenshot" for item in sample_summaries
            ),
            "region_count": len(results),
            "matched_regions": matches,
            "mismatched_regions": len(results) - matches,
            "match_rate": round(matches / len(results), 4),
            "expected_counts": expected_counts,
            "actual_counts": actual_counts,
            "status": "pass" if matches == len(results) else "review",
        },
        "samples": sample_summaries,
        "regions": results,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_markdown.write_text(_markdown(report), encoding="utf-8")
    return report


def _required_text(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CalibrationError(f"Missing required text field: {field}")
    return value


def _parse_region(
    payload: dict, sample_id: str, width: int, height: int
) -> CalibrationRegion:
    expected = _required_text(payload, "expected")
    if expected not in {"low", "review", "high"}:
        raise CalibrationError(f"Invalid expected risk for {sample_id}: {expected}")
    try:
        coordinates = [float(payload[key]) for key in ("x0", "y0", "x1", "y1")]
    except (KeyError, TypeError, ValueError) as error:
        raise CalibrationError(f"Invalid region coordinates for {sample_id}") from error
    x0, y0, x1, y1 = coordinates
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise CalibrationError(f"Out-of-bounds region for {sample_id}: {coordinates}")
    return CalibrationRegion(
        id=_required_text(payload, "id"),
        label=_required_text(payload, "label"),
        expected=expected,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
    )


def _markdown(report: dict) -> str:
    summary = report["summary"]
    rows = [
        "| Sample | Type | Region | Expected | Actual | Texture | Edge | Periodic | Structure |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for item in report["regions"]:
        scores = item["scores"]
        actual = item["actual"] if item["matched"] else f"**{item['actual']}**"
        rows.append(
            f"| {item['sample_id']} | {item['kind']} | {item['label']} | "
            f"{item['expected']} | {actual} | {scores['texture']:.4f} | "
            f"{scores['edge_density']:.4f} | {scores['periodicity']:.4f} | "
            f"{scores['structure']:.4f} |"
        )

    sources = []
    for sample in report["samples"]:
        record = sample["source_record"]
        source_label = f"[source record]({record})" if record else "local project capture"
        terms = sample["usage_terms_url"]
        terms_label = f"[usage terms]({terms})" if terms else "repository-owned"
        sources.extend(
            [
                f"### {sample['id']}",
                "",
                f"- File: `{sample['file']}` (`{sample['sha256']}`)",
                f"- Dimensions: {sample['width']} × {sample['height']}",
                f"- Attribution: {sample['attribution']}",
                f"- Provenance: {sample['provenance_note']}",
                f"- References: {source_label}; {terms_label}",
                "",
            ]
        )

    rationales = [
        f"- `{item['sample_id']}:{item['region_id']}` ({item['expected']}): "
        f"{item['label_rationale']}"
        for item in report["regions"]
    ]

    versions = report["versions"]
    thresholds = report["thresholds"]
    return "\n".join(
        [
            "# Image complexity calibration",
            "",
            (
                "This audit checks the production preflight against provenance-recorded "
                "photos and a repository-owned browser screenshot. Exact source bytes are "
                "pinned by SHA-256."
            ),
            "",
            f"Status: **{summary['status']}** · Samples: {summary['sample_count']} · "
            f"Regions: {summary['region_count']} · Matches: {summary['matched_regions']} · "
            f"Mismatches: {summary['mismatched_regions']} · "
            f"Match rate: {summary['match_rate'] * 100:.2f}%",
            "",
            f"OpenCV: `{versions['opencv']}` · NumPy: `{versions['numpy']}` · "
            f"Pillow: `{versions['pillow']}`",
            "",
            f"Labeling protocol: {report['labeling_protocol']}",
            "",
            (
                "Thresholds: "
                f"periodicity high `{thresholds['periodicity_high']}` · "
                f"periodicity minimum texture `{thresholds['periodicity_min_texture']}` · "
                f"structure high `{thresholds['structure_high']}` · "
                f"edge high `{thresholds['edge_high']}` · "
                f"texture review `{thresholds['texture_review']}` · "
                f"edge review `{thresholds['edge_review']}`"
            ),
            "",
            *rows,
            "",
            "## Label rationale",
            "",
            *rationales,
            "",
            "## Provenance",
            "",
            *sources,
            "## Interpretation",
            "",
            (
                "The labels describe expected preflight risk for the selected regions, not "
                "reconstruction quality. A passing audit shows that threshold behavior remains "
                "stable on these pinned samples; it does not establish accuracy on arbitrary "
                "photos."
            ),
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit image complexity thresholds.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero when any expected risk differs."
    )
    args = parser.parse_args()
    report = run_calibration(
        args.manifest,
        report_json=args.report_json,
        report_markdown=args.report_md,
    )
    if args.strict and report["summary"]["mismatched_regions"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
