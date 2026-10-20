from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT.parent
SOURCE_ROOT = FIXTURE_ROOT / "mask_refinement_holdout_sources"
DEVELOPMENT_MANIFEST = FIXTURE_ROOT / "vlm_localization" / "mask-refinement-photo-manifest.json"
MASK_ROOT = ROOT / "expected"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _corner_badge(clean: Image.Image) -> tuple[Image.Image, dict[str, int], str]:
    layer = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    box = {"x0": 500, "y0": 390, "x1": 692, "y1": 448}
    draw.rounded_rectangle((500, 390, 691, 447), radius=12, fill=(10, 20, 27, 176))
    draw.text((520, 407), "@SAMPLE", font=_font(22), fill=(255, 255, 255, 244))
    return Image.alpha_composite(clean.convert("RGBA"), layer).convert("RGB"), box, "corner_badge"


def _top_preview(clean: Image.Image) -> tuple[Image.Image, dict[str, int], str]:
    raw = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(raw)
    draw.text(
        (12, 12),
        "PREVIEW",
        font=_font(44),
        fill=(255, 255, 255, 92),
        stroke_width=1,
        stroke_fill=(12, 18, 30, 72),
    )
    glyph = raw.crop(raw.getbbox())
    glyph = glyph.crop(glyph.getchannel("A").getbbox())
    xy = (254, 36)
    layer = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    layer.alpha_composite(glyph, xy)
    box = {"x0": xy[0], "y0": xy[1], "x1": xy[0] + glyph.width, "y1": xy[1] + glyph.height}
    return (
        Image.alpha_composite(clean.convert("RGBA"), layer).convert("RGB"),
        box,
        "translucent_text",
    )


def build() -> None:
    source_manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    sources = source_manifest.get("sources")
    if (
        source_manifest.get("schema_version") != 1
        or source_manifest.get("corpus_role") != "independent_holdout"
        or not isinstance(sources, list)
        or len(sources) != 8
    ):
        raise ValueError("Holdout source manifest must contain eight reserved sources.")
    development = json.loads(DEVELOPMENT_MANIFEST.read_text(encoding="utf-8"))
    development_groups = {sample["source_group"] for sample in development["samples"]}
    development_digests = {sample["source_sha256"] for sample in development["samples"]}
    holdout_groups = {source["source_group"] for source in sources}
    holdout_digests = {source["sha256"] for source in sources}
    if (
        len(holdout_groups) != 8
        or len(holdout_digests) != 8
        or development_groups & holdout_groups
        or development_digests & holdout_digests
    ):
        raise ValueError("Holdout sources must be unique and disjoint from development sources.")

    MASK_ROOT.mkdir(parents=True, exist_ok=True)
    samples: list[dict] = []
    predictions: list[dict] = []
    painters = (_corner_badge, _top_preview) * 4
    for source, painter in zip(sources, painters, strict=True):
        source_path = SOURCE_ROOT / source["file"]
        if not source_path.is_file() or _sha256(source_path) != source["sha256"]:
            raise ValueError(f"Holdout source digest mismatch: {source['file']}")
        with Image.open(source_path) as image:
            clean = ImageOps.fit(
                ImageOps.exif_transpose(image).convert("RGB"),
                (720, 480),
                method=Image.Resampling.LANCZOS,
            )
        marked, candidate, overlay_kind = painter(clean)
        pair_id = source["nasa_id"].lower()
        clean_path = ROOT / f"paired-{pair_id}-clean.png"
        marked_path = ROOT / f"paired-{pair_id}-watermark.png"
        clean.save(clean_path, format="PNG", compress_level=9)
        marked.save(marked_path, format="PNG", compress_level=9)
        clean_pixels = np.asarray(clean, dtype=np.uint8)
        marked_pixels = np.asarray(marked, dtype=np.uint8)
        changed = np.any(clean_pixels != marked_pixels, axis=2)
        outside = changed.copy()
        outside[candidate["y0"] : candidate["y1"], candidate["x0"] : candidate["x1"]] = False
        if not changed.any() or outside.any():
            raise ValueError(f"Invalid generated holdout overlay: {pair_id}")

        common = {
            "width": 720,
            "height": 480,
            "candidate_box": candidate,
            "review_required": False,
            "pair_id": pair_id,
            "source_group": source["source_group"],
            "source_sha256": source["sha256"],
            "source_record": source["record_url"],
            "usage_terms_url": source["license_url"],
            "license": source["license"],
            "attribution": f"{source['credit']} — {source['title']}",
            "contains_user_data": False,
            "provenance": (
                "Pinned public NASA photograph reserved before holdout inference; the positive "
                "overlay is repository-generated and the negative is its clean pair."
            ),
        }
        for role, image_path, truth, category in (
            ("clean_negative", clean_path, np.zeros_like(changed), f"clean_{overlay_kind}_context"),
            ("watermark_positive", marked_path, changed, overlay_kind),
        ):
            sample_id = (
                f"holdout-{pair_id}-{'negative' if role == 'clean_negative' else 'positive'}"
            )
            mask_path = MASK_ROOT / f"{sample_id}.png"
            Image.fromarray(truth.astype(np.uint8) * 255, mode="L").save(mask_path, format="PNG")
            samples.append(
                {
                    "id": sample_id,
                    "file": image_path.name,
                    "sha256": _sha256(image_path),
                    "expected_mask": f"expected/{mask_path.name}",
                    "expected_mask_sha256": _sha256(mask_path),
                    "category": category,
                    "pair_role": role,
                    "transformation": (
                        f"Deterministic 720x480 normalization plus {overlay_kind} overlay."
                        if role == "watermark_positive"
                        else "Deterministic 720x480 normalization with no watermark overlay."
                    ),
                    "annotation_method": (
                        "Exact RGB pixel difference against the paired clean image."
                        if role == "watermark_positive"
                        else "Reviewed clean counterpart; expected mask is empty."
                    ),
                    **common,
                }
            )
            predictions.append(
                {
                    "sample_id": sample_id,
                    "mask_file": f"expected/{mask_path.name}",
                    "mask_sha256": _sha256(mask_path),
                    "runtime": None,
                    "workflow_seconds": None,
                }
            )

    manifest = {
        "schema_version": 1,
        "corpus_kind": "provenance_photo_pairs",
        "corpus_role": "independent_holdout",
        "frozen_before_model_inference": True,
        "development_source_manifest": "../vlm_localization/mask-refinement-photo-manifest.json",
        "description": (
            "Independent eight-source, sixteen-sample holdout for candidate confirmation."
        ),
        "samples": samples,
    }
    contract = {
        "schema_version": 1,
        "refiner": {
            "id": "holdout-scoring-contract",
            "model_id": None,
            "model_revision": None,
            "prompt_version": "paired-holdout-truth-v1",
            "device": "fixture",
            "is_model_output": False,
            "automatic_download": False,
        },
        "predictions": predictions,
    }
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ROOT / "contract-predictions.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build()
