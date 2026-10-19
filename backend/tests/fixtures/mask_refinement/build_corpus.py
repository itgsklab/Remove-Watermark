from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
SIZE = (128, 96)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _save_sample(
    sample_id: str,
    category: str,
    candidate_box: tuple[int, int, int, int],
    draw_content,
    draw_truth=None,
) -> tuple[dict[str, object], dict[str, object]]:
    image = Image.new("RGB", SIZE, "#d9e2e8")
    content = ImageDraw.Draw(image)
    content.rectangle((0, 64, 127, 95), fill="#8ba3ad")
    draw_content(content)
    source_path = ROOT / "images" / f"{sample_id}.png"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(source_path, format="PNG", optimize=False)

    truth = Image.new("L", SIZE, 0)
    if draw_truth is not None:
        draw_truth(ImageDraw.Draw(truth))
    truth_path = ROOT / "expected" / f"{sample_id}.png"
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    truth.save(truth_path, format="PNG", optimize=False)

    predicted_path = ROOT / "predicted" / f"{sample_id}.png"
    predicted_path.parent.mkdir(parents=True, exist_ok=True)
    truth.save(predicted_path, format="PNG", optimize=False)

    manifest_row = {
        "id": sample_id,
        "file": f"images/{source_path.name}",
        "sha256": _sha(source_path),
        "expected_mask": f"expected/{truth_path.name}",
        "expected_mask_sha256": _sha(truth_path),
        "width": SIZE[0],
        "height": SIZE[1],
        "category": category,
        "candidate_box": dict(zip(("x0", "y0", "x1", "y1"), candidate_box, strict=True)),
        "review_required": False,
        "provenance": "Deterministic repository-generated scoring-contract fixture.",
    }
    prediction_row = {
        "sample_id": sample_id,
        "mask_file": f"predicted/{predicted_path.name}",
        "mask_sha256": _sha(predicted_path),
        "runtime": None,
        "workflow_seconds": None,
    }
    return manifest_row, prediction_row


def build() -> None:
    samples = []
    predictions = []

    def add(*args, **kwargs) -> None:
        sample, prediction = _save_sample(*args, **kwargs)
        samples.append(sample)
        predictions.append(prediction)

    def translucent(draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle((30, 31, 97, 54), fill="#91a6ad")
        for x in range(34, 94, 12):
            draw.rectangle((x, 36, x + 7, 49), fill="#eff4f5")

    def translucent_mask(draw: ImageDraw.ImageDraw) -> None:
        for x in range(34, 94, 12):
            draw.rectangle((x, 36, x + 7, 49), fill=255)

    add(
        "positive-translucent-text",
        "translucent_text",
        (26, 27, 102, 59),
        translucent,
        translucent_mask,
    )

    def timestamp(draw: ImageDraw.ImageDraw) -> None:
        for x in (45, 57, 75, 87):
            draw.rectangle((x, 73, x + 7, 78), fill="#f4f6f7")
            draw.rectangle((x, 81, x + 7, 86), fill="#f4f6f7")

    def timestamp_mask(draw: ImageDraw.ImageDraw) -> None:
        for x in (45, 57, 75, 87):
            draw.rectangle((x, 73, x + 7, 78), fill=255)
            draw.rectangle((x, 81, x + 7, 86), fill=255)

    add("positive-timestamp", "timestamp", (40, 69, 100, 91), timestamp, timestamp_mask)

    def stamp(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((87, 10, 116, 39), outline="#b94b43", width=4)
        draw.line((93, 25, 110, 25), fill="#b94b43", width=3)

    def stamp_mask(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((87, 10, 116, 39), outline=255, width=4)
        draw.line((93, 25, 110, 25), fill=255, width=3)

    add("positive-stamp", "stamp", (83, 6, 121, 44), stamp, stamp_mask)

    signature_points = [(15, 53), (29, 45), (40, 58), (55, 41), (72, 55)]

    def signature(draw: ImageDraw.ImageDraw) -> None:
        draw.line(signature_points, fill="#f2f5f6", width=3)

    def signature_mask(draw: ImageDraw.ImageDraw) -> None:
        draw.line(signature_points, fill=255, width=3)

    add("positive-signature", "signature", (10, 36, 78, 63), signature, signature_mask)

    def face(draw: ImageDraw.ImageDraw) -> None:
        draw.ellipse((45, 12, 82, 49), fill="#d8a67d")
        draw.ellipse((55, 25, 58, 28), fill="#27333a")
        draw.ellipse((69, 25, 72, 28), fill="#27333a")
        draw.arc((56, 28, 72, 40), 10, 170, fill="#7b4d3e", width=2)

    add("negative-face", "face", (40, 8, 87, 54), face)

    def content_signature(draw: ImageDraw.ImageDraw) -> None:
        draw.line((19, 47, 34, 37, 49, 52, 68, 35, 84, 49), fill="#24343d", width=3)

    add("negative-content-signature", "normal_signature", (14, 30, 90, 58), content_signature)

    def brand(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle((88, 12, 116, 40), radius=6, fill="#246b85")
        draw.rectangle((97, 19, 107, 33), fill="#d9e2e8")

    add("negative-brand", "brand", (84, 8, 120, 44), brand)

    def body_text(draw: ImageDraw.ImageDraw) -> None:
        for y, width in ((16, 72), (25, 83), (34, 65), (43, 78)):
            draw.rectangle((13, y, 13 + width, y + 3), fill="#4e626c")

    add("negative-body-text", "body_text", (8, 11, 102, 51), body_text)

    (ROOT / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "description": "Model-independent box-guided mask-refinement scoring fixtures.",
                "samples": samples,
            },
            indent=2,
        )
        + "\n"
    )
    (ROOT / "contract-predictions.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "refiner": {
                    "id": "mask-refinement-contract-fixture",
                    "model_id": None,
                    "model_revision": None,
                    "prompt_version": "mask-refinement-contract-v1",
                    "device": "fixture",
                    "is_model_output": False,
                    "automatic_download": False,
                    "note": "Geometry fixture for the scoring contract; not a model result.",
                },
                "predictions": predictions,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    build()
