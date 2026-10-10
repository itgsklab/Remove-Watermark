from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wmrm.adapters.images.florence2 import Florence2Localizer
from wmrm.adapters.images.photo_scene import PhotoGatedLocalizer, WatermarkLocalizer

DEFAULT_PROMPT = "watermark"


def generate_predictions(
    corpus_manifest: Path,
    model_dir: Path,
    model_manifest: Path,
    output: Path,
    *,
    prompt: str = DEFAULT_PROMPT,
    device: str = "auto",
    localizer: WatermarkLocalizer | None = None,
    use_photo_scene_gate: bool = False,
) -> dict[str, Any]:
    corpus_manifest = corpus_manifest.resolve()
    corpus = json.loads(corpus_manifest.read_text(encoding="utf-8"))
    if corpus.get("schema_version") != 1 or not isinstance(corpus.get("samples"), list):
        raise ValueError("Unsupported localization corpus manifest.")
    detector = localizer or Florence2Localizer(model_dir, model_manifest, device=device)
    if use_photo_scene_gate:
        detector = PhotoGatedLocalizer(detector)
    rows = []
    for sample in corpus["samples"]:
        sample_id = sample.get("id")
        relative = sample.get("file")
        if not isinstance(sample_id, str) or not isinstance(relative, str):
            raise ValueError("Invalid localization corpus sample.")
        image_path = (corpus_manifest.parent / relative).resolve()
        fixture_root = corpus_manifest.parent.parent.resolve()
        if fixture_root not in image_path.parents or not image_path.is_file():
            raise ValueError(f"Invalid corpus image path: {relative}")
        boxes = detector.localize(image_path, prompt)
        rows.append(
            {
                "sample_id": sample_id,
                "boxes": [
                    {
                        "x0": box.x0,
                        "y0": box.y0,
                        "x1": box.x1,
                        "y1": box.y1,
                        "label": box.label,
                        "confidence": box.confidence,
                    }
                    for box in boxes
                ],
            }
        )
    result = {
        "schema_version": 1,
        "detector": {
            "id": "florence-2-local-open-vocabulary",
            "model_id": detector.model_id,
            "model_revision": detector.model_revision,
            "prompt": prompt,
            "is_model_output": True,
            "runtime": getattr(detector, "runtime_metadata", {"kind": "injected"}),
            "note": "Generated locally from SHA-256 verified Safetensors weights.",
        },
        "predictions": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Florence-2 localization predictions.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="auto")
    parser.add_argument("--photo-scene-gate", action="store_true")
    args = parser.parse_args()
    generate_predictions(
        args.manifest,
        args.model_dir,
        args.model_manifest,
        args.output,
        prompt=args.prompt,
        device=args.device,
        use_photo_scene_gate=args.photo_scene_gate,
    )


if __name__ == "__main__":
    main()
