from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wmrm.adapters.images.photo_scene import PhotoSceneGate, photo_scene_gate_metadata
from wmrm.benchmarks.vlm_localization import run_localization_benchmark

MINIMUM_INDEPENDENT_PHOTO_SOURCES = 10


def evaluate_photo_gate(
    manifest_path: Path,
    predictions_path: Path,
    *,
    gated_predictions_path: Path,
    localization_report_json: Path,
    localization_report_markdown: Path,
    gate_report_json: Path,
    gate_report_markdown: Path,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    predictions_path = predictions_path.resolve()
    manifest = _load(manifest_path)
    predictions = _load(predictions_path)
    samples = manifest.get("samples")
    prediction_rows = predictions.get("predictions")
    if manifest.get("schema_version") != 1 or not isinstance(samples, list):
        raise ValueError("Unsupported localization manifest.")
    if predictions.get("schema_version") != 1 or not isinstance(prediction_rows, list):
        raise ValueError("Unsupported localization predictions.")
    prediction_map = {row["sample_id"]: row for row in prediction_rows}
    if len(prediction_map) != len(prediction_rows):
        raise ValueError("Predictions contain duplicate samples.")

    gate = PhotoSceneGate()
    rows = []
    gated_rows = []
    photo_sources: set[str] = set()
    for sample in samples:
        sample_id = _text(sample, "id")
        relative = _text(sample, "file")
        scene_kind = _text(sample, "scene_kind")
        source_group = _text(sample, "source_group")
        image_path = (manifest_path.parent / relative).resolve()
        if not image_path.is_file():
            raise ValueError(f"Missing localization sample: {sample_id}")
        prediction = prediction_map.get(sample_id)
        if not isinstance(prediction, dict) or not isinstance(prediction.get("boxes"), list):
            raise ValueError(f"Missing prediction row: {sample_id}")
        expected_photo = scene_kind == "natural_scene"
        if expected_photo:
            photo_sources.add(source_group)
        assessment = gate.assess(image_path)
        rows.append(
            {
                "sample_id": sample_id,
                "scene_kind": scene_kind,
                "source_group": source_group,
                "expected_photo": expected_photo,
                "eligible": assessment.eligible,
                "luminance_entropy": assessment.luminance_entropy,
                "quantized_color_count": assessment.quantized_color_count,
                "classification_correct": assessment.eligible == expected_photo,
            }
        )
        gated_rows.append(
            {
                "sample_id": sample_id,
                "boxes": prediction["boxes"] if assessment.eligible else [],
            }
        )

    detector = dict(predictions.get("detector", {}))
    detector["id"] = f"photo-scene-gated-{detector.get('id', 'localizer')}"
    detector["runtime"] = {
        **(detector.get("runtime") if isinstance(detector.get("runtime"), dict) else {}),
        "photo_scene_gate": photo_scene_gate_metadata(),
    }
    detector["note"] = (
        "Derived from pinned real model output after a deterministic pixel-only photo gate."
    )
    gated_predictions = {
        "schema_version": 1,
        "detector": detector,
        "predictions": gated_rows,
    }
    gated_predictions_path.parent.mkdir(parents=True, exist_ok=True)
    gated_predictions_path.write_text(
        json.dumps(gated_predictions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    localization = run_localization_benchmark(
        manifest_path,
        gated_predictions_path,
        report_json=localization_report_json,
        report_markdown=localization_report_markdown,
        require_model_output=True,
    )

    true_positive = sum(row["expected_photo"] and row["eligible"] for row in rows)
    false_positive = sum(not row["expected_photo"] and row["eligible"] for row in rows)
    false_negative = sum(row["expected_photo"] and not row["eligible"] for row in rows)
    true_negative = sum(not row["expected_photo"] and not row["eligible"] for row in rows)
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    specificity = _ratio(true_negative, true_negative + false_positive)
    pair_groups: dict[str, list[dict[str, Any]]] = {}
    for sample, row in zip(samples, rows, strict=True):
        pair_id = sample.get("pair_id")
        if isinstance(pair_id, str):
            pair_groups.setdefault(pair_id, []).append(row)
    stable_pairs = sum(
        len(members) == 2 and len({item["eligible"] for item in members}) == 1
        for members in pair_groups.values()
    )
    natural_metrics = next(
        row for row in localization["scene_breakdown"] if row["scene_kind"] == "natural_scene"
    )
    source_gate_passed = len(photo_sources) >= MINIMUM_INDEPENDENT_PHOTO_SOURCES
    report = {
        "schema_version": 1,
        "benchmark": "wmrm-vlm-photo-scene-gate",
        "thresholds": detector["runtime"]["photo_scene_gate"],
        "summary": {
            "sample_count": len(rows),
            "expected_photo_count": sum(row["expected_photo"] for row in rows),
            "expected_non_photo_count": sum(not row["expected_photo"] for row in rows),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "specificity": round(specificity, 6),
            "stable_pair_count": stable_pairs,
            "pair_count": len(pair_groups),
            "independent_photo_source_count": len(photo_sources),
            "minimum_independent_photo_sources": MINIMUM_INDEPENDENT_PHOTO_SOURCES,
            "source_evidence_gate": "pass" if source_gate_passed else "fail",
            "release_claim_allowed": (
                precision == 1.0
                and recall == 1.0
                and specificity == 1.0
                and stable_pairs == len(pair_groups)
                and natural_metrics["precision"] >= 0.75
                and natural_metrics["recall"] >= 0.85
                and source_gate_passed
            ),
        },
        "eligible_localization": natural_metrics,
        "samples": rows,
    }
    gate_report_json.parent.mkdir(parents=True, exist_ok=True)
    gate_report_markdown.parent.mkdir(parents=True, exist_ok=True)
    gate_report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    gate_report_markdown.write_text(_markdown(report), encoding="utf-8")
    return report


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path.name}")
    return value


def _text(value: dict[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"Missing text field: {field}")
    return result


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def _markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    localization = report["eligible_localization"]
    rows = [
        "| Sample | Expected | Eligible | Entropy | Colors | Correct |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for sample in report["samples"]:
        rows.append(
            f"| {sample['sample_id']} | {'photo' if sample['expected_photo'] else 'other'} | "
            f"{'yes' if sample['eligible'] else 'no'} | {sample['luminance_entropy']:.4f} | "
            f"{sample['quantized_color_count']} | "
            f"{'yes' if sample['classification_correct'] else 'no'} |"
        )
    return "\n".join(
        [
            "# VLM photo-scene gate benchmark",
            "",
            f"Gate classification: Precision **{summary['precision']:.3f}** · "
            f"Recall **{summary['recall']:.3f}** · Specificity **{summary['specificity']:.3f}**",
            f"Pair stability: **{summary['stable_pair_count']}/{summary['pair_count']}** · "
            f"Independent photo sources: **{summary['independent_photo_source_count']}/"
            f"{summary['minimum_independent_photo_sources']}** · "
            f"Source evidence gate: **{summary['source_evidence_gate']}**",
            f"Eligible photo localization: Precision **{localization['precision']:.3f}** · "
            f"Recall **{localization['recall']:.3f}** · F1 **{localization['f1']:.3f}**",
            "",
            *rows,
            "",
            "The gate is not release-ready until independent photo-source evidence passes.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the conservative VLM photo gate.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--gated-predictions", type=Path, required=True)
    parser.add_argument("--localization-report-json", type=Path, required=True)
    parser.add_argument("--localization-report-md", type=Path, required=True)
    parser.add_argument("--gate-report-json", type=Path, required=True)
    parser.add_argument("--gate-report-md", type=Path, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate_photo_gate(
        args.manifest,
        args.predictions,
        gated_predictions_path=args.gated_predictions,
        localization_report_json=args.localization_report_json,
        localization_report_markdown=args.localization_report_md,
        gate_report_json=args.gate_report_json,
        gate_report_markdown=args.gate_report_md,
    )
    if args.strict and not report["summary"]["release_claim_allowed"]:
        raise SystemExit("Photo-scene gate release evidence failed.")


if __name__ == "__main__":
    main()
