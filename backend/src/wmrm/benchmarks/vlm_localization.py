from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox, intersection_over_union


class LocalizationBenchmarkError(ValueError):
    pass


def run_localization_benchmark(
    manifest_path: Path,
    predictions_path: Path,
    *,
    report_json: Path,
    report_markdown: Path,
    iou_threshold: float = 0.5,
    min_precision: float = 0.75,
    min_recall: float = 0.85,
    require_model_output: bool = False,
) -> dict[str, Any]:
    if not 0 < iou_threshold <= 1:
        raise LocalizationBenchmarkError("IoU threshold must be in (0, 1].")
    if not 0 <= min_precision <= 1 or not 0 <= min_recall <= 1:
        raise LocalizationBenchmarkError("Precision and recall thresholds must be in [0, 1].")
    manifest_path = manifest_path.resolve()
    predictions_path = predictions_path.resolve()
    manifest = _load_json(manifest_path)
    predictions = _load_json(predictions_path)
    if manifest.get("schema_version") != 1 or predictions.get("schema_version") != 1:
        raise LocalizationBenchmarkError("Unsupported localization benchmark schema.")
    detector = predictions.get("detector")
    if not isinstance(detector, dict):
        raise LocalizationBenchmarkError("Predictions must describe the detector.")
    is_model_output = _required_bool(detector, "is_model_output")
    if require_model_output and not is_model_output:
        raise LocalizationBenchmarkError("A real model output is required for this benchmark run.")

    samples = manifest.get("samples")
    prediction_rows = predictions.get("predictions")
    if not isinstance(samples, list) or not samples:
        raise LocalizationBenchmarkError("Localization corpus must contain samples.")
    if not isinstance(prediction_rows, list):
        raise LocalizationBenchmarkError("Predictions must contain a list of sample rows.")
    prediction_map: dict[str, dict[str, Any]] = {}
    for row in prediction_rows:
        if not isinstance(row, dict):
            raise LocalizationBenchmarkError("Prediction rows must be objects.")
        sample_id = _required_text(row, "sample_id")
        if sample_id in prediction_map:
            raise LocalizationBenchmarkError(f"Duplicate prediction row: {sample_id}")
        prediction_map[sample_id] = row

    results = []
    expected_ids: set[str] = set()
    totals = {"true_positive": 0, "false_positive": 0, "false_negative": 0}
    matched_ious: list[float] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise LocalizationBenchmarkError("Corpus samples must be objects.")
        sample_id = _required_text(sample, "id")
        if sample_id in expected_ids:
            raise LocalizationBenchmarkError(f"Duplicate corpus sample: {sample_id}")
        expected_ids.add(sample_id)
        if sample.get("review_required") is not False:
            raise LocalizationBenchmarkError(f"Sample {sample_id} requires manual review.")
        image_path = _contained_file(manifest_path.parent, _required_text(sample, "file"))
        _verify_sha(image_path, _required_text(sample, "sha256"))
        width = _required_int(sample, "width")
        height = _required_int(sample, "height")
        with Image.open(image_path) as image:
            if image.size != (width, height):
                raise LocalizationBenchmarkError(f"Dimension mismatch for {sample_id}.")
        expected = _boxes(sample.get("expected_regions"), width, height, confidence=1.0)
        row = prediction_map.get(sample_id)
        if row is None:
            raise LocalizationBenchmarkError(f"Missing prediction row: {sample_id}")
        actual = _boxes(row.get("boxes"), width, height)
        score = _score_sample(expected, actual, iou_threshold)
        for key in totals:
            totals[key] += score[key]
        matched_ious.extend(score["matched_ious"])
        results.append(
            {
                "sample_id": sample_id,
                "kind": "positive" if expected else "negative",
                "expected_count": len(expected),
                "predicted_count": len(actual),
                "true_positive": score["true_positive"],
                "false_positive": score["false_positive"],
                "false_negative": score["false_negative"],
                "matched_ious": [round(value, 6) for value in score["matched_ious"]],
            }
        )
    extras = sorted(set(prediction_map) - expected_ids)
    if extras:
        raise LocalizationBenchmarkError(f"Predictions contain unknown samples: {extras}")

    precision = _ratio(totals["true_positive"], totals["true_positive"] + totals["false_positive"])
    recall = _ratio(totals["true_positive"], totals["true_positive"] + totals["false_negative"])
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    mean_iou = sum(matched_ious) / len(matched_ious) if matched_ious else 0.0
    gate_passed = precision >= min_precision and recall >= min_recall
    report = {
        "schema_version": 1,
        "benchmark": "wmrm-vlm-watermark-localization",
        "evaluation_kind": "model" if is_model_output else "contract_fixture",
        "detector": detector,
        "thresholds": {
            "iou": iou_threshold,
            "minimum_precision": min_precision,
            "minimum_recall": min_recall,
        },
        "summary": {
            "sample_count": len(results),
            "positive_count": sum(item["kind"] == "positive" for item in results),
            "negative_count": sum(item["kind"] == "negative" for item in results),
            **totals,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "mean_matched_iou": round(mean_iou, 6),
            "metric_gate": "pass" if gate_passed else "fail",
            "release_claim_allowed": is_model_output and gate_passed,
        },
        "samples": results,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_markdown.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    report_markdown.write_text(_markdown(report))
    return report


def _score_sample(
    expected: list[LocalizationBox], actual: list[LocalizationBox], threshold: float
) -> dict[str, Any]:
    matches: list[float] = []
    unmatched_expected = set(range(len(expected)))
    for predicted in sorted(actual, key=lambda item: item.confidence, reverse=True):
        candidates = [
            (intersection_over_union(predicted, expected[index]), index)
            for index in unmatched_expected
        ]
        best_iou, best_index = max(candidates, default=(0.0, -1))
        if best_iou >= threshold:
            unmatched_expected.remove(best_index)
            matches.append(best_iou)
    true_positive = len(matches)
    return {
        "true_positive": true_positive,
        "false_positive": len(actual) - true_positive,
        "false_negative": len(expected) - true_positive,
        "matched_ious": matches,
    }


def _boxes(
    values: object, width: int, height: int, *, confidence: float | None = None
) -> list[LocalizationBox]:
    if not isinstance(values, list):
        raise LocalizationBenchmarkError("Localization boxes must be a list.")
    boxes = []
    for value in values:
        if not isinstance(value, dict):
            raise LocalizationBenchmarkError("Localization boxes must be objects.")
        try:
            box = LocalizationBox(
                x0=_required_number(value, "x0"),
                y0=_required_number(value, "y0"),
                x1=_required_number(value, "x1"),
                y1=_required_number(value, "y1"),
                label=_required_text(value, "label"),
                confidence=(
                    confidence
                    if confidence is not None
                    else _required_number(value, "confidence")
                ),
            )
        except ValueError as exc:
            raise LocalizationBenchmarkError(str(exc)) from exc
        if box.x1 > width or box.y1 > height:
            raise LocalizationBenchmarkError("Localization box leaves image bounds.")
        boxes.append(box)
    return boxes


def _contained_file(root: Path, relative: str) -> Path:
    boundary = root.parent.resolve()
    path = (root / relative).resolve()
    if boundary != path and boundary not in path.parents:
        raise LocalizationBenchmarkError(f"Corpus path leaves fixture root: {relative}")
    if not path.is_file():
        raise LocalizationBenchmarkError(f"Missing corpus file: {relative}")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LocalizationBenchmarkError(f"Cannot read JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise LocalizationBenchmarkError(f"JSON root must be an object: {path.name}")
    return value


def _verify_sha(path: Path, expected: str) -> None:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise LocalizationBenchmarkError(f"SHA-256 mismatch for {path.name}.")


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise LocalizationBenchmarkError(f"Missing required text field: {field}")
    return value


def _required_bool(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise LocalizationBenchmarkError(f"Missing required boolean field: {field}")
    return value


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise LocalizationBenchmarkError(f"Invalid positive integer field: {field}")
    return value


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise LocalizationBenchmarkError(f"Missing required numeric field: {field}")
    return float(value)


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 1.0


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = [
        "| Sample | Kind | Expected | Predicted | TP | FP | FN | IoU |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for sample in report["samples"]:
        ious = sample["matched_ious"]
        rows.append(
            f"| {sample['sample_id']} | {sample['kind']} | {sample['expected_count']} | "
            f"{sample['predicted_count']} | {sample['true_positive']} | "
            f"{sample['false_positive']} | {sample['false_negative']} | "
            f"{', '.join(f'{value:.3f}' for value in ious) if ious else '—'} |"
        )
    claim = (
        "This report contains real model output."
        if report["evaluation_kind"] == "model"
        else "This is a geometry contract fixture, not a model performance result."
    )
    return "\n".join(
        [
            "# VLM watermark-localization benchmark",
            "",
            claim,
            "",
            f"Metric gate: **{summary['metric_gate']}** · Precision: {summary['precision']:.3f} · "
            f"Recall: {summary['recall']:.3f} · F1: {summary['f1']:.3f} · "
            f"Mean matched IoU: {summary['mean_matched_iou']:.3f}",
            "",
            *rows,
            "",
            "A release claim is allowed only when `evaluation_kind` is `model` "
            "and the metric gate passes.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Score watermark-localization predictions.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-md", type=Path, required=True)
    parser.add_argument("--require-model-output", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_localization_benchmark(
        args.manifest,
        args.predictions,
        report_json=args.report_json,
        report_markdown=args.report_md,
        require_model_output=args.require_model_output,
    )
    if args.strict and report["summary"]["metric_gate"] != "pass":
        raise SystemExit("Localization metric gate failed.")


if __name__ == "__main__":
    main()
