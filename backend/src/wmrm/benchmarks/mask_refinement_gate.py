from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

DEFAULT_IOU_THRESHOLD = 0.5


class CandidateGateError(ValueError):
    pass


def apply_candidate_confirmation_gate(
    corpus_manifest: Path,
    localization_predictions: Path,
    segmentation_predictions: Path,
    output: Path,
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> dict[str, Any]:
    if not 0 < iou_threshold <= 1:
        raise CandidateGateError("Candidate IoU threshold must be in (0, 1].")
    corpus_manifest = corpus_manifest.resolve()
    localization_predictions = localization_predictions.resolve()
    segmentation_predictions = segmentation_predictions.resolve()
    corpus = _load_json(corpus_manifest)
    localization = _load_json(localization_predictions)
    segmentation = _load_json(segmentation_predictions)
    if any(payload.get("schema_version") != 1 for payload in (corpus, localization, segmentation)):
        raise CandidateGateError("Unsupported candidate-gate schema.")

    detector = localization.get("detector")
    refiner = segmentation.get("refiner")
    if not isinstance(detector, dict) or detector.get("is_model_output") is not True:
        raise CandidateGateError("Candidate gate requires real localization model output.")
    if not isinstance(refiner, dict) or refiner.get("is_model_output") is not True:
        raise CandidateGateError("Candidate gate requires real segmentation model output.")
    if detector.get("prompt") != "watermark":
        raise CandidateGateError("Candidate gate requires the pinned watermark prompt.")
    if detector.get("automatic_download") not in (None, False):
        raise CandidateGateError("Localization weights must not download automatically.")
    if refiner.get("automatic_download") is not False:
        raise CandidateGateError("Segmentation weights must not download automatically.")

    samples = corpus.get("samples")
    if corpus.get("corpus_kind") != "provenance_photo_pairs" or not isinstance(samples, list):
        raise CandidateGateError("Candidate gate requires the audited photo-pair corpus.")
    localization_map = _row_map(localization.get("predictions"), "localization")
    segmentation_map = _row_map(segmentation.get("predictions"), "segmentation")
    output = output.resolve()
    mask_root = output.parent / "gated_masks"
    mask_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    counts = {"true_positive": 0, "true_negative": 0, "false_positive": 0, "false_negative": 0}

    for sample in samples:
        if not isinstance(sample, dict):
            raise CandidateGateError("Corpus samples must be objects.")
        sample_id = _required_text(sample, "id")
        width = _required_int(sample, "width")
        height = _required_int(sample, "height")
        expected_positive = sample.get("pair_role") == "watermark_positive"
        if sample.get("pair_role") not in {"watermark_positive", "clean_negative"}:
            raise CandidateGateError(f"Invalid photo-pair role for {sample_id}.")
        candidate = _box(sample.get("candidate_box"), width, height)
        localization_row = localization_map.get(sample_id)
        segmentation_row = segmentation_map.get(sample_id)
        if localization_row is None or segmentation_row is None:
            raise CandidateGateError(f"Missing model prediction for {sample_id}.")
        detections = localization_row.get("boxes")
        if not isinstance(detections, list):
            raise CandidateGateError(f"Invalid localization boxes for {sample_id}.")
        best_iou = max(
            (_intersection_over_union(candidate, _box(item, width, height)) for item in detections),
            default=0.0,
        )
        accepted = best_iou >= iou_threshold
        if accepted:
            outcome = "true_positive" if expected_positive else "false_positive"
        else:
            outcome = "false_negative" if expected_positive else "true_negative"
        counts[outcome] += 1

        mask_path = mask_root / f"{sample_id}.png"
        if accepted:
            source_mask = _contained_file(
                segmentation_predictions.parent,
                _required_text(segmentation_row, "mask_file"),
            )
            _verify_sha(source_mask, _required_text(segmentation_row, "mask_sha256"))
            with Image.open(source_mask) as source:
                if source.mode != "L" or source.size != (width, height):
                    raise CandidateGateError(f"Invalid segmentation mask for {sample_id}.")
                mask = np.asarray(source, dtype=np.uint8)
            if not np.isin(mask, (0, 255)).all():
                raise CandidateGateError(f"Segmentation mask is not binary for {sample_id}.")
        else:
            mask = np.zeros((height, width), dtype=np.uint8)
        Image.fromarray(mask).save(mask_path, format="PNG", optimize=False)
        rows.append(
            {
                "sample_id": sample_id,
                "mask_file": f"gated_masks/{mask_path.name}",
                "mask_sha256": _sha256(mask_path),
                "runtime": segmentation_row.get("runtime"),
                "workflow_seconds": segmentation_row.get("workflow_seconds"),
            }
        )
        diagnostics.append(
            {
                "sample_id": sample_id,
                "expected": "accept" if expected_positive else "reject",
                "decision": "accept" if accepted else "reject",
                "best_iou": round(best_iou, 6),
                "outcome": outcome,
            }
        )

    expected_ids = {_required_text(sample, "id") for sample in samples if isinstance(sample, dict)}
    if set(segmentation_map) != expected_ids:
        raise CandidateGateError("Segmentation predictions do not exactly match the corpus.")
    precision = _ratio(counts["true_positive"], counts["true_positive"] + counts["false_positive"])
    recall = _ratio(counts["true_positive"], counts["true_positive"] + counts["false_negative"])
    gate = {
        "kind": "florence2-candidate-iou-confirmation",
        "iou_threshold": iou_threshold,
        "detector_id": _required_text(detector, "id"),
        "detector_model_id": _required_text(detector, "model_id"),
        "detector_model_revision": _required_text(detector, "model_revision"),
        "prompt": "watermark",
        **counts,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "samples": diagnostics,
    }
    segmentation_id = _required_text(refiner, "id")
    segmentation_prompt = _required_text(refiner, "prompt_version")
    result = {
        "schema_version": 1,
        "refiner": {
            "id": f"florence2-confirmed-{segmentation_id}",
            "model_id": f"{gate['detector_model_id']} + {_required_text(refiner, 'model_id')}",
            "model_revision": (
                f"{gate['detector_model_revision']} + {_required_text(refiner, 'model_revision')}"
            ),
            "prompt_version": f"watermark-candidate-iou-v1 + {segmentation_prompt}",
            "device": _required_text(refiner, "device"),
            "is_model_output": True,
            "automatic_download": False,
            "runtime": refiner.get("runtime"),
            "candidate_gate": gate,
        },
        "predictions": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _row_map(value: object, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        raise CandidateGateError(f"Missing {label} prediction rows.")
    result: dict[str, dict[str, Any]] = {}
    for row in value:
        if not isinstance(row, dict):
            raise CandidateGateError(f"Invalid {label} prediction row.")
        sample_id = _required_text(row, "sample_id")
        if sample_id in result:
            raise CandidateGateError(f"Duplicate {label} prediction for {sample_id}.")
        result[sample_id] = row
    return result


def _box(value: object, width: int, height: int) -> tuple[float, float, float, float]:
    if not isinstance(value, dict):
        raise CandidateGateError("Candidate boxes must be objects.")
    coordinates = tuple(_required_number(value, field) for field in ("x0", "y0", "x1", "y1"))
    x0, y0, x1, y1 = coordinates
    if x0 < 0 or y0 < 0 or x0 >= x1 or y0 >= y1 or x1 > width or y1 > height:
        raise CandidateGateError("Candidate box leaves image bounds.")
    return coordinates


def _intersection_over_union(
    left: tuple[float, float, float, float], right: tuple[float, float, float, float]
) -> float:
    intersection_width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    intersection_height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    intersection = intersection_width * intersection_height
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _contained_file(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    root = root.resolve()
    if root not in path.parents or not path.is_file():
        raise CandidateGateError("Segmentation mask leaves its prediction directory.")
    return path


def _verify_sha(path: Path, expected: str) -> None:
    if _sha256(path) != expected:
        raise CandidateGateError(f"Mask SHA-256 mismatch for {path.name}.")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateGateError(f"Cannot read candidate-gate JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise CandidateGateError("Candidate-gate JSON root must be an object.")
    return value


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CandidateGateError(f"Missing required text field: {field}")
    return value.strip()


def _required_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CandidateGateError(f"Invalid positive integer field: {field}")
    return value


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise CandidateGateError(f"Missing required numeric field: {field}")
    return float(value)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 1.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Confirm candidate boxes with pinned localization output before SAM2 refinement."
        )
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--localization-predictions", type=Path, required=True)
    parser.add_argument("--segmentation-predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iou-threshold", type=float, default=DEFAULT_IOU_THRESHOLD)
    args = parser.parse_args()
    apply_candidate_confirmation_gate(
        args.manifest,
        args.localization_predictions,
        args.segmentation_predictions,
        args.output,
        iou_threshold=args.iou_threshold,
    )


if __name__ == "__main__":
    main()
