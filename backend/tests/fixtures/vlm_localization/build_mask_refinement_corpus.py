from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT.parent
OUTPUT_MANIFEST = ROOT / "mask-refinement-photo-manifest.json"
OUTPUT_PREDICTIONS = ROOT / "mask-refinement-photo-contract-predictions.json"
MASK_ROOT = ROOT / "mask_refinement_expected"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected an object in {path.name}.")
    return value


def _source_records() -> dict[str, dict[str, str]]:
    photo_manifest = _load_json(FIXTURE_ROOT / "vlm_photo_sources" / "manifest.json")
    records: dict[str, dict[str, str]] = {}
    for source in photo_manifest["sources"]:
        source_path = FIXTURE_ROOT / "vlm_photo_sources" / source["file"]
        if not source_path.is_file() or _sha256(source_path) != source["sha256"]:
            raise ValueError(f"Photo source digest mismatch: {source['file']}.")
        records[source["source_group"]] = {
            "source_sha256": source["sha256"],
            "source_record": source["record_url"],
            "usage_terms_url": source["license_url"],
            "license": source["license"],
            "attribution": f"{source['credit']} — {source['title']}",
        }

    complexity = _load_json(FIXTURE_ROOT / "image_complexity" / "manifest.json")
    by_file = {sample["file"]: sample for sample in complexity["samples"]}
    for source_group, filename in {
        "nasa-iss074e0089803": "nasa-earth-iss074e0089803.jpg",
        "nasa-iss045e013851": "nasa-earth-iss045e013851.jpg",
    }.items():
        source = by_file[filename]
        source_path = FIXTURE_ROOT / "image_complexity" / filename
        if not source_path.is_file() or _sha256(source_path) != source["sha256"]:
            raise ValueError(f"Complexity source digest mismatch: {filename}.")
        records[source_group] = {
            "source_sha256": source["sha256"],
            "source_record": source["source_record"],
            "usage_terms_url": source["usage_terms_url"],
            "license": "NASA media usage guidelines",
            "attribution": source["attribution"],
        }
    return records


def build() -> None:
    localization = _load_json(ROOT / "manifest.json")
    photo_samples = [
        sample
        for sample in localization["samples"]
        if sample.get("scene_kind") == "natural_scene" and sample.get("pair_id") is not None
    ]
    pairs: dict[str, dict[str, dict]] = {}
    for sample in photo_samples:
        role = "watermark_positive" if sample["expected_regions"] else "clean_negative"
        pairs.setdefault(sample["pair_id"], {})[role] = sample
    if len(pairs) != 16 or any(
        set(pair) != {"clean_negative", "watermark_positive"} for pair in pairs.values()
    ):
        raise ValueError("Expected sixteen complete natural-scene pairs.")

    sources = _source_records()
    MASK_ROOT.mkdir(parents=True, exist_ok=True)
    manifest_rows: list[dict] = []
    prediction_rows: list[dict] = []
    for pair_id, pair in sorted(pairs.items()):
        clean_row = pair["clean_negative"]
        positive_row = pair["watermark_positive"]
        source_group = clean_row["source_group"]
        if source_group != positive_row["source_group"] or source_group not in sources:
            raise ValueError(f"Missing or inconsistent source record for {pair_id}.")
        regions = positive_row["expected_regions"]
        if len(regions) != 1:
            raise ValueError(f"Expected one candidate region for {pair_id}.")
        box = {key: int(regions[0][key]) for key in ("x0", "y0", "x1", "y1")}

        clean_path = ROOT / clean_row["file"]
        positive_path = ROOT / positive_row["file"]
        if (
            _sha256(clean_path) != clean_row["sha256"]
            or _sha256(positive_path) != positive_row["sha256"]
        ):
            raise ValueError(f"Localization fixture digest mismatch for {pair_id}.")
        with Image.open(clean_path) as clean_source, Image.open(positive_path) as marked_source:
            clean = np.asarray(clean_source.convert("RGB"), dtype=np.uint8)
            marked = np.asarray(marked_source.convert("RGB"), dtype=np.uint8)
        if clean.shape != marked.shape:
            raise ValueError(f"Pair dimensions differ for {pair_id}.")
        changed = np.any(clean != marked, axis=2)
        if not changed.any():
            raise ValueError(f"Positive pair contains no changed pixels: {pair_id}.")
        outside = changed.copy()
        outside[box["y0"] : box["y1"], box["x0"] : box["x1"]] = False
        if outside.any():
            raise ValueError(f"Positive truth leaves the candidate box: {pair_id}.")

        height, width = changed.shape
        overlay_kind = "corner_badge" if box["x0"] == 500 else "translucent_text"
        for role, source_row, truth, category in (
            ("clean_negative", clean_row, np.zeros_like(changed), f"clean_{overlay_kind}_context"),
            ("watermark_positive", positive_row, changed, overlay_kind),
        ):
            sample_id = source_row["id"]
            mask_path = MASK_ROOT / f"{sample_id}.png"
            Image.fromarray(truth.astype(np.uint8) * 255, mode="L").save(
                mask_path,
                format="PNG",
                optimize=False,
            )
            source_metadata = sources[source_group]
            manifest_rows.append(
                {
                    "id": sample_id,
                    "file": source_row["file"],
                    "sha256": source_row["sha256"],
                    "expected_mask": f"mask_refinement_expected/{mask_path.name}",
                    "expected_mask_sha256": _sha256(mask_path),
                    "width": width,
                    "height": height,
                    "category": category,
                    "candidate_box": box,
                    "review_required": False,
                    "pair_id": pair_id,
                    "pair_role": role,
                    "source_group": source_group,
                    **source_metadata,
                    "contains_user_data": False,
                    "provenance": (
                        "Pinned public real photograph normalized by the repository; the positive "
                        "overlay is repository-generated and the negative is its clean pair."
                    ),
                    "transformation": (
                        (
                            "Deterministic 720x480 normalization followed by repository-generated "
                            f"{overlay_kind.replace('_', ' ')} overlay."
                        )
                        if role == "watermark_positive"
                        else "Deterministic 720x480 normalization with no watermark overlay."
                    ),
                    "annotation_method": (
                        "Exact RGB pixel difference against the paired clean image."
                        if role == "watermark_positive"
                        else "Reviewed clean counterpart; expected mask is empty."
                    ),
                }
            )
            prediction_rows.append(
                {
                    "sample_id": sample_id,
                    "mask_file": f"mask_refinement_expected/{mask_path.name}",
                    "mask_sha256": _sha256(mask_path),
                    "runtime": None,
                    "workflow_seconds": None,
                }
            )

    manifest = {
        "schema_version": 1,
        "corpus_kind": "provenance_photo_pairs",
        "description": (
            "Paired real-photo mask-refinement corpus built from pinned NASA and Wikimedia "
            "sources with repository-generated overlays and exact pixel-difference truth."
        ),
        "samples": manifest_rows,
    }
    predictions = {
        "schema_version": 1,
        "refiner": {
            "id": "photo-corpus-scoring-contract",
            "model_id": None,
            "model_revision": None,
            "prompt_version": "paired-photo-truth-v1",
            "device": "fixture",
            "is_model_output": False,
            "automatic_download": False,
            "note": "Ground-truth masks for contract verification; not model output.",
        },
        "predictions": prediction_rows,
    }
    OUTPUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    OUTPUT_PREDICTIONS.write_text(json.dumps(predictions, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
