from __future__ import annotations

import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from wmrm.adapters.images.detection import LocalizationBox
from wmrm.adapters.images.sam2 import Sam2MaskRefiner
from wmrm.adapters.images.segmentation import WatermarkMaskRefiner


def generate_mask_predictions(
    corpus_manifest: Path,
    model_dir: Path,
    model_manifest: Path,
    output: Path,
    *,
    device: str = "auto",
    refiner: WatermarkMaskRefiner | None = None,
) -> dict[str, Any]:
    corpus_manifest = corpus_manifest.resolve()
    corpus = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    samples = corpus.get("samples")
    if corpus.get("schema_version") != 1 or not isinstance(samples, list) or not samples:
        raise ValueError("Unsupported mask-refinement corpus manifest.")
    segmenter = refiner or Sam2MaskRefiner(
        model_dir,
        model_manifest,
        device=device,
    )
    output = output.resolve()
    mask_dir = output.parent / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    fixture_root = corpus_manifest.parent.resolve()
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("Corpus sample must be an object.")
        sample_id = _required_text(sample, "id")
        image_path = (fixture_root / _required_text(sample, "file")).resolve()
        if fixture_root not in image_path.parents or not image_path.is_file():
            raise ValueError("Corpus image leaves the fixture directory.")
        box_value = sample.get("candidate_box")
        if not isinstance(box_value, dict):
            raise ValueError("Corpus sample requires a candidate box.")
        box = LocalizationBox(
            x0=_required_number(box_value, "x0"),
            y0=_required_number(box_value, "y0"),
            x1=_required_number(box_value, "x1"),
            y1=_required_number(box_value, "y1"),
            label="candidate",
            confidence=1.0,
        )
        started = time.perf_counter()
        mask = segmenter.refine(image_path, (box,))
        duration_ms = (time.perf_counter() - started) * 1000
        mask_path = mask_dir / f"{sample_id}.png"
        pixels = np.frombuffer(mask.pixels, dtype=np.uint8).reshape(mask.height, mask.width)
        Image.fromarray(pixels * 255).save(mask_path, format="PNG", optimize=False)
        rows.append(
            {
                "sample_id": sample_id,
                "mask_file": mask_path.relative_to(output.parent).as_posix(),
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
                "runtime": {
                    "duration_ms": round(duration_ms, 3),
                    "peak_memory_mb": round(_peak_rss_mb(), 3),
                },
                "workflow_seconds": None,
            }
        )
    metadata = dict(segmenter.runtime_metadata)
    result = {
        "schema_version": 1,
        "refiner": {
            "id": "sam2-hiera-tiny-box-refiner-v1",
            "model_id": segmenter.model_id,
            "model_revision": segmenter.model_revision,
            "prompt_version": "candidate-box-v1",
            "device": str(metadata.get("device", device)),
            "is_model_output": True,
            "automatic_download": False,
            "runtime": metadata,
        },
        "predictions": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def _peak_rss_mb() -> float:
    value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform != "darwin":
        value *= 1024
    return value / (1024 * 1024)


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing corpus field: {field}")
    return value.strip()


def _required_number(payload: dict[str, Any], field: str) -> float:
    value = payload.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"Invalid candidate coordinate: {field}")
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate real SAM2 mask-refinement predictions.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    args = parser.parse_args()
    generate_mask_predictions(
        args.manifest,
        args.model_dir,
        args.model_manifest,
        args.output,
        device=args.device,
    )


if __name__ == "__main__":
    main()
