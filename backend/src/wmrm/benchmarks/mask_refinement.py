from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import numpy as np
from PIL import Image

MAX_IMAGE_DIMENSION = 10_000
MAX_IMAGE_PIXELS = 40_000_000


class MaskRefinementBenchmarkError(ValueError):
    pass


def run_mask_refinement_benchmark(
    manifest_path: Path,
    predictions_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
    min_iou: float = 0.75,
    min_precision: float = 0.80,
    min_recall: float = 0.80,
    min_correction_reduction: float = 0.25,
    min_sample_count: int = 8,
    min_negative_count: int = 4,
    min_category_count: int = 6,
    min_timing_count: int = 6,
    require_model_output: bool = False,
) -> dict[str, Any]:
    for name, value in {
        "minimum IoU": min_iou,
        "minimum precision": min_precision,
        "minimum recall": min_recall,
        "minimum correction reduction": min_correction_reduction,
    }.items():
        if not 0 <= value <= 1:
            raise MaskRefinementBenchmarkError(f"{name} must be in [0, 1].")
    if any(
        value < 1
        for value in (
            min_sample_count,
            min_negative_count,
            min_category_count,
            min_timing_count,
        )
    ):
        raise MaskRefinementBenchmarkError("Evidence thresholds must be positive.")

    manifest_path = manifest_path.resolve()
    predictions_path = predictions_path.resolve()
    manifest = _load_json(manifest_path)
    predictions = _load_json(predictions_path)
    if manifest.get("schema_version") != 1 or predictions.get("schema_version") != 1:
        raise MaskRefinementBenchmarkError("Unsupported mask-refinement benchmark schema.")

    refiner = predictions.get("refiner")
    if not isinstance(refiner, dict):
        raise MaskRefinementBenchmarkError("Predictions must describe the refiner.")
    is_model_output = _required_bool(refiner, "is_model_output")
    if require_model_output and not is_model_output:
        raise MaskRefinementBenchmarkError(
            "A real model output is required for this benchmark run."
        )
    _validate_refiner_metadata(refiner, require_runtime=is_model_output)

    samples = manifest.get("samples")
    prediction_rows = predictions.get("predictions")
    if not isinstance(samples, list) or not samples:
        raise MaskRefinementBenchmarkError("Mask-refinement corpus must contain samples.")
    corpus_audit = _audit_corpus_metadata(manifest, samples)
    if not isinstance(prediction_rows, list):
        raise MaskRefinementBenchmarkError("Predictions must contain sample rows.")
    prediction_map = _prediction_map(prediction_rows)

    results: list[dict[str, Any]] = []
    expected_ids: set[str] = set()
    totals = {
        "true_positive_pixels": 0,
        "false_positive_pixels": 0,
        "false_negative_pixels": 0,
        "candidate_correction_pixels": 0,
        "refined_correction_pixels": 0,
        "outside_candidate_pixels": 0,
    }
    timing_rows: list[dict[str, float]] = []
    categories: set[str] = set()
    negative_count = 0

    for sample in samples:
        if not isinstance(sample, dict):
            raise MaskRefinementBenchmarkError("Corpus samples must be objects.")
        sample_id = _required_text(sample, "id")
        if sample_id in expected_ids:
            raise MaskRefinementBenchmarkError(f"Duplicate corpus sample: {sample_id}")
        expected_ids.add(sample_id)
        if sample.get("review_required") is not False:
            raise MaskRefinementBenchmarkError(f"Sample {sample_id} requires manual review.")
        category = _required_text(sample, "category")
        categories.add(category)
        image_path = _contained_file(manifest_path.parent, _required_text(sample, "file"))
        _verify_sha(image_path, _required_text(sample, "sha256"))
        width = _required_int(sample, "width")
        height = _required_int(sample, "height")
        if (
            width > MAX_IMAGE_DIMENSION
            or height > MAX_IMAGE_DIMENSION
            or width * height > MAX_IMAGE_PIXELS
        ):
            raise MaskRefinementBenchmarkError(f"Image limits exceeded for {sample_id}.")
        with Image.open(image_path) as image:
            if image.size != (width, height):
                raise MaskRefinementBenchmarkError(f"Dimension mismatch for {sample_id}.")
        expected = _load_mask(
            manifest_path.parent,
            _required_text(sample, "expected_mask"),
            _required_text(sample, "expected_mask_sha256"),
            width,
            height,
        )
        is_negative = not bool(expected.any())
        if corpus_audit is not None:
            expected_role = "clean_negative" if is_negative else "watermark_positive"
            if sample.get("pair_role") != expected_role:
                raise MaskRefinementBenchmarkError(
                    f"Pair role does not match mask truth for {sample_id}."
                )
        negative_count += int(is_negative)
        candidate_box = _candidate_box(sample.get("candidate_box"), width, height)
        candidate = _box_mask(candidate_box, width, height)

        row = prediction_map.get(sample_id)
        if row is None:
            raise MaskRefinementBenchmarkError(f"Missing prediction row: {sample_id}")
        predicted = _load_mask(
            predictions_path.parent,
            _required_text(row, "mask_file"),
            _required_text(row, "mask_sha256"),
            width,
            height,
        )
        runtime = _runtime_metrics(row, required=is_model_output)
        workflow = _workflow_timing(row)
        if workflow is not None:
            timing_rows.append(workflow)

        true_positive = int(np.logical_and(expected, predicted).sum())
        false_positive = int(np.logical_and(~expected, predicted).sum())
        false_negative = int(np.logical_and(expected, ~predicted).sum())
        candidate_correction = int(np.logical_xor(candidate, expected).sum())
        refined_correction = false_positive + false_negative
        outside_candidate = int(np.logical_and(predicted, ~candidate).sum())
        for key, value in {
            "true_positive_pixels": true_positive,
            "false_positive_pixels": false_positive,
            "false_negative_pixels": false_negative,
            "candidate_correction_pixels": candidate_correction,
            "refined_correction_pixels": refined_correction,
            "outside_candidate_pixels": outside_candidate,
        }.items():
            totals[key] += value
        sample_union = true_positive + false_positive + false_negative
        sample_iou = true_positive / sample_union if sample_union else 1.0
        sample_reduction = _correction_reduction(candidate_correction, refined_correction)
        results.append(
            {
                "sample_id": sample_id,
                "kind": "negative" if is_negative else "positive",
                "category": category,
                "expected_pixels": int(expected.sum()),
                "candidate_pixels": int(candidate.sum()),
                "predicted_pixels": int(predicted.sum()),
                "true_positive_pixels": true_positive,
                "false_positive_pixels": false_positive,
                "false_negative_pixels": false_negative,
                "outside_candidate_pixels": outside_candidate,
                "iou": round(sample_iou, 6),
                "candidate_correction_pixels": candidate_correction,
                "refined_correction_pixels": refined_correction,
                "correction_reduction": round(sample_reduction, 6),
                "runtime": runtime,
                "workflow_seconds": workflow,
            }
        )

    extras = sorted(set(prediction_map) - expected_ids)
    if extras:
        raise MaskRefinementBenchmarkError(f"Predictions contain unknown samples: {extras}")

    tp = totals["true_positive_pixels"]
    fp = totals["false_positive_pixels"]
    fn = totals["false_negative_pixels"]
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 1.0
    reduction = _correction_reduction(
        totals["candidate_correction_pixels"], totals["refined_correction_pixels"]
    )
    metric_gate = (
        iou >= min_iou
        and precision >= min_precision
        and recall >= min_recall
        and reduction >= min_correction_reduction
        and totals["outside_candidate_pixels"] == 0
    )
    evidence_gate = (
        len(results) >= min_sample_count
        and negative_count >= min_negative_count
        and len(categories) >= min_category_count
    )
    timing_gate = len(timing_rows) >= min_timing_count
    report = {
        "schema_version": 1,
        "benchmark": "wmrm-box-guided-mask-refinement",
        "evaluation_kind": "model" if is_model_output else "contract_fixture",
        "refiner": refiner,
        "thresholds": {
            "minimum_iou": min_iou,
            "minimum_precision": min_precision,
            "minimum_recall": min_recall,
            "minimum_correction_reduction": min_correction_reduction,
            "maximum_outside_candidate_pixels": 0,
            "minimum_sample_count": min_sample_count,
            "minimum_negative_count": min_negative_count,
            "minimum_category_count": min_category_count,
            "minimum_timing_count": min_timing_count,
        },
        "summary": {
            "sample_count": len(results),
            "positive_count": len(results) - negative_count,
            "negative_count": negative_count,
            "category_count": len(categories),
            **totals,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "iou": round(iou, 6),
            "correction_reduction": round(reduction, 6),
            "timing_evidence_count": len(timing_rows),
            "metric_gate": "pass" if metric_gate else "fail",
            "evidence_gate": "pass" if evidence_gate else "fail",
            "timing_gate": "pass" if timing_gate else "fail",
            "release_claim_allowed": (
                is_model_output and metric_gate and evidence_gate and timing_gate
            ),
        },
        "workflow_timing": _timing_summary(timing_rows),
        "samples": results,
    }
    if corpus_audit is not None:
        report["corpus"] = corpus_audit
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    report_markdown.write_text(_markdown(report))
    return report


def _prediction_map(rows: list[object]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise MaskRefinementBenchmarkError("Prediction rows must be objects.")
        sample_id = _required_text(row, "sample_id")
        if sample_id in result:
            raise MaskRefinementBenchmarkError(f"Duplicate prediction row: {sample_id}")
        result[sample_id] = row
    return result


def _audit_corpus_metadata(
    manifest: dict[str, Any], samples: list[object]
) -> dict[str, Any] | None:
    kind = manifest.get("corpus_kind")
    if kind is None:
        return None
    if kind != "provenance_photo_pairs":
        raise MaskRefinementBenchmarkError("Unsupported mask-refinement corpus kind.")
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    sources: set[str] = set()
    for sample in samples:
        if not isinstance(sample, dict):
            raise MaskRefinementBenchmarkError("Corpus samples must be objects.")
        pair_id = _required_text(sample, "pair_id")
        role = _required_text(sample, "pair_role")
        if role not in {"clean_negative", "watermark_positive"}:
            raise MaskRefinementBenchmarkError("Photo pair role is invalid.")
        if role in pairs.setdefault(pair_id, {}):
            raise MaskRefinementBenchmarkError(f"Duplicate {role} row for pair {pair_id}.")
        pairs[pair_id][role] = sample
        source_group = _required_text(sample, "source_group")
        sources.add(source_group)
        source_sha256 = _required_text(sample, "source_sha256")
        if len(source_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in source_sha256
        ):
            raise MaskRefinementBenchmarkError("source_sha256 must be a lowercase SHA-256 value.")
        _required_text(sample, "license")
        _required_text(sample, "attribution")
        _required_text(sample, "provenance")
        _required_text(sample, "transformation")
        _required_text(sample, "annotation_method")
        if sample.get("contains_user_data") is not False:
            raise MaskRefinementBenchmarkError("Photo corpus must exclude user data.")
        for field in ("source_record", "usage_terms_url"):
            value = _required_text(sample, field)
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username is not None:
                raise MaskRefinementBenchmarkError(f"{field} must be a public HTTPS URL.")

    required_roles = {"clean_negative", "watermark_positive"}
    for pair_id, pair in pairs.items():
        if set(pair) != required_roles:
            raise MaskRefinementBenchmarkError(f"Incomplete photo pair: {pair_id}.")
        negative = pair["clean_negative"]
        positive = pair["watermark_positive"]
        for field in (
            "width",
            "height",
            "candidate_box",
            "source_group",
            "source_sha256",
            "source_record",
            "usage_terms_url",
            "license",
            "attribution",
        ):
            if negative.get(field) != positive.get(field):
                raise MaskRefinementBenchmarkError(
                    f"Photo pair metadata mismatch for {pair_id}: {field}."
                )
        if negative.get("file") == positive.get("file") or negative.get("sha256") == positive.get(
            "sha256"
        ):
            raise MaskRefinementBenchmarkError(f"Photo pair images are not distinct: {pair_id}.")
    if len(sources) != len(pairs):
        raise MaskRefinementBenchmarkError("Each photo pair must use an independent source group.")
    return {
        "kind": kind,
        "provenance_gate": "pass",
        "pair_count": len(pairs),
        "source_count": len(sources),
        "contains_user_data": False,
    }


def _validate_refiner_metadata(refiner: dict[str, Any], *, require_runtime: bool) -> None:
    _required_text(refiner, "id")
    _required_text(refiner, "prompt_version")
    if refiner.get("automatic_download") is not False:
        raise MaskRefinementBenchmarkError("Mask-refiner weights must not download automatically.")
    if require_runtime:
        _required_text(refiner, "model_id")
        _required_text(refiner, "model_revision")
        _required_text(refiner, "device")


def _runtime_metrics(row: dict[str, Any], *, required: bool) -> dict[str, float] | None:
    value = row.get("runtime")
    if value is None and not required:
        return None
    if not isinstance(value, dict):
        raise MaskRefinementBenchmarkError("Model predictions require runtime metrics.")
    duration_ms = _required_number(value, "duration_ms")
    peak_memory_mb = _required_number(value, "peak_memory_mb")
    if duration_ms <= 0 or peak_memory_mb < 0:
        raise MaskRefinementBenchmarkError("Runtime metrics must be non-negative and timed.")
    return {"duration_ms": duration_ms, "peak_memory_mb": peak_memory_mb}


def _workflow_timing(row: dict[str, Any]) -> dict[str, float] | None:
    value = row.get("workflow_seconds")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise MaskRefinementBenchmarkError("Workflow timing must be an object.")
    result = {key: _required_number(value, key) for key in ("manual", "box", "refined")}
    if any(item <= 0 for item in result.values()):
        raise MaskRefinementBenchmarkError("Workflow timing values must be positive.")
    return result


def _timing_summary(rows: list[dict[str, float]]) -> dict[str, float | int | None]:
    if not rows:
        return {"count": 0, "manual_mean": None, "box_mean": None, "refined_mean": None}
    return {
        "count": len(rows),
        "manual_mean": round(sum(row["manual"] for row in rows) / len(rows), 6),
        "box_mean": round(sum(row["box"] for row in rows) / len(rows), 6),
        "refined_mean": round(sum(row["refined"] for row in rows) / len(rows), 6),
    }


def _candidate_box(value: object, width: int, height: int) -> tuple[int, int, int, int]:
    if not isinstance(value, dict):
        raise MaskRefinementBenchmarkError("Each sample requires a candidate box.")
    coordinates = tuple(_required_int(value, key) for key in ("x0", "y0", "x1", "y1"))
    x0, y0, x1, y1 = coordinates
    if x0 < 0 or y0 < 0 or x0 >= x1 or y0 >= y1 or x1 > width or y1 > height:
        raise MaskRefinementBenchmarkError("Candidate box leaves image bounds.")
    return coordinates


def _box_mask(box: tuple[int, int, int, int], width: int, height: int) -> np.ndarray:
    x0, y0, x1, y1 = box
    mask = np.zeros((height, width), dtype=bool)
    mask[y0:y1, x0:x1] = True
    return mask


def _load_mask(
    root: Path,
    relative: str,
    expected_sha: str,
    width: int,
    height: int,
) -> np.ndarray:
    path = _contained_file(root, relative)
    _verify_sha(path, expected_sha)
    with Image.open(path) as image:
        if image.mode != "L" or image.size != (width, height):
            raise MaskRefinementBenchmarkError("Mask must be an aligned 8-bit grayscale image.")
        values = np.asarray(image, dtype=np.uint8)
    if not np.isin(values, (0, 255)).all():
        raise MaskRefinementBenchmarkError("Mask pixels must be exactly 0 or 255.")
    return values == 255


def _correction_reduction(candidate: int, refined: int) -> float:
    if candidate == 0:
        return 1.0 if refined == 0 else 0.0
    return max(0.0, min(1.0, 1 - refined / candidate))


def _contained_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    root = root.resolve()
    if path == root or root not in path.parents or not path.is_file():
        raise MaskRefinementBenchmarkError("Benchmark file leaves its fixture directory.")
    return path


def _verify_sha(path: Path, expected: str) -> None:
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise MaskRefinementBenchmarkError("Invalid SHA-256 value.")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise MaskRefinementBenchmarkError(f"SHA-256 mismatch for {path.name}.")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise MaskRefinementBenchmarkError(f"Cannot read benchmark JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise MaskRefinementBenchmarkError("Benchmark JSON root must be an object.")
    return value


def _required_text(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise MaskRefinementBenchmarkError(f"{key} must be non-empty text.")
    return result


def _required_bool(value: dict[str, Any], key: str) -> bool:
    result = value.get(key)
    if not isinstance(result, bool):
        raise MaskRefinementBenchmarkError(f"{key} must be a boolean.")
    return result


def _required_int(value: dict[str, Any], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise MaskRefinementBenchmarkError(f"{key} must be an integer.")
    if key in {"width", "height"} and result <= 0:
        raise MaskRefinementBenchmarkError(f"{key} must be positive.")
    return result


def _required_number(value: dict[str, Any], key: str) -> float:
    result = value.get(key)
    if not isinstance(result, int | float) or isinstance(result, bool):
        raise MaskRefinementBenchmarkError(f"{key} must be numeric.")
    number = float(result)
    if not np.isfinite(number):
        raise MaskRefinementBenchmarkError(f"{key} must be finite.")
    return number


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = [
        "| Sample | Kind | Category | IoU | Box correction | Refined correction | Reduction |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    rows.extend(
        f"| {sample['sample_id']} | {sample['kind']} | {sample['category']} | "
        f"{sample['iou']:.3f} | {sample['candidate_correction_pixels']} | "
        f"{sample['refined_correction_pixels']} | {sample['correction_reduction']:.3f} |"
        for sample in report["samples"]
    )
    note = (
        "This report contains real model output."
        if report["evaluation_kind"] == "model"
        else "This is a scoring-contract fixture, not a model performance result."
    )
    lines = [
        "# Box-guided mask-refinement benchmark",
        "",
        note,
        "",
        f"Metric gate: **{summary['metric_gate']}** · IoU: {summary['iou']:.3f} · "
        f"Precision: {summary['precision']:.3f} · Recall: {summary['recall']:.3f}",
        f"Correction reduction: {summary['correction_reduction']:.3f} · "
        f"Outside-box pixels: {summary['outside_candidate_pixels']}",
        f"Evidence gate: **{summary['evidence_gate']}** · Samples: "
        f"{summary['sample_count']} · Negatives: {summary['negative_count']} · "
        f"Categories: {summary['category_count']}",
        f"Timing gate: **{summary['timing_gate']}** · Timed workflows: "
        f"{summary['timing_evidence_count']}",
    ]
    corpus = report.get("corpus")
    if isinstance(corpus, dict):
        lines.append(
            f"Provenance gate: **{corpus['provenance_gate']}** · Independent sources: "
            f"{corpus['source_count']} · Paired scenes: {corpus['pair_count']}"
        )
    candidate_gate = report["refiner"].get("candidate_gate")
    if isinstance(candidate_gate, dict):
        lines.append(
            "Candidate gate: "
            f"TP {candidate_gate['true_positive']} · TN {candidate_gate['true_negative']} · "
            f"FP {candidate_gate['false_positive']} · FN {candidate_gate['false_negative']} · "
            f"Precision {candidate_gate['precision']:.3f} · "
            f"Recall {candidate_gate['recall']:.3f}"
        )
    return "\n".join(
        [
            *lines,
            "",
            "## Samples",
            "",
            *rows,
            "",
            "A release claim requires real model output plus metric, evidence and human timing "
            "gates. Model output remains a review-only draft.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score box-guided mask-refinement predictions.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--require-model-output", action="store_true")
    parser.add_argument("--min-sample-count", type=int, default=8)
    parser.add_argument("--min-negative-count", type=int, default=4)
    parser.add_argument("--min-category-count", type=int, default=6)
    parser.add_argument("--min-timing-count", type=int, default=6)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_mask_refinement_benchmark(
        args.manifest,
        args.predictions,
        report_json=args.report_json,
        report_markdown=args.report_md,
        require_model_output=args.require_model_output,
        min_sample_count=args.min_sample_count,
        min_negative_count=args.min_negative_count,
        min_category_count=args.min_category_count,
        min_timing_count=args.min_timing_count,
    )
    if args.strict and not report["summary"]["release_claim_allowed"]:
        raise SystemExit("Mask-refinement release-evidence gate failed.")


if __name__ == "__main__":
    main()
