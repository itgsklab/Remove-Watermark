import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = ROOT.parent / "image_complexity"
SIZE = (540, 720)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    horizon = _portrait_crop(
        SOURCE_ROOT / "nasa-earth-iss074e0089803.jpg", (370, 0, 909, 718)
    )
    night = _portrait_crop(
        SOURCE_ROOT / "nasa-earth-iss045e013851.jpg", (120, 0, 758, 851)
    )
    samples = [
        _corner_sample(horizon),
        _translucent_sample(horizon),
        _multiline_sample(night),
    ]
    manifest = {
        "schema_version": 1,
        "description": (
            "Portrait derivatives of provenance-recorded real photographs with "
            "repository-generated watermark overlays."
        ),
        "samples": samples,
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _portrait_crop(path: Path, box: tuple[int, int, int, int]) -> Image.Image:
    with Image.open(path) as source:
        return source.convert("RGB").crop(box).resize(SIZE, Image.Resampling.LANCZOS)


def _corner_sample(clean: Image.Image) -> dict:
    region = {"x0": 400, "y0": 30, "x1": 520, "y1": 74}
    image = clean.convert("RGBA")
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((400, 30, 519, 73), radius=10, fill=(8, 16, 28, 165))
    draw.text(
        (412, 40),
        "@sample",
        font=ImageFont.load_default(size=17),
        fill=(255, 255, 255, 238),
    )
    return _save_sample(
        "real-horizon-corner",
        Image.alpha_composite(image, overlay).convert("RGB"),
        region,
        expected_low_contrast=False,
        source_file="../image_complexity/nasa-earth-iss074e0089803.jpg",
        source_sha256="d88909464177af39f24ed97ae28f4eab383c2b477f4a7e00e716812252227d11",
        source_record="https://images.nasa.gov/details/iss074e0089803",
        transformation="Center portrait crop, 540x720 resize, opaque corner badge overlay.",
    )


def _translucent_sample(clean: Image.Image) -> dict:
    region = {"x0": 90, "y0": 120, "x1": 450, "y1": 220}
    image = clean.convert("RGBA")
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.text(
        (126, 144),
        "SAMPLE",
        font=ImageFont.load_default(size=52),
        fill=(255, 255, 255, 58),
        stroke_width=1,
        stroke_fill=(20, 25, 30, 35),
    )
    return _save_sample(
        "real-horizon-translucent",
        Image.alpha_composite(image, overlay).convert("RGB"),
        region,
        expected_low_contrast=True,
        source_file="../image_complexity/nasa-earth-iss074e0089803.jpg",
        source_sha256="d88909464177af39f24ed97ae28f4eab383c2b477f4a7e00e716812252227d11",
        source_record="https://images.nasa.gov/details/iss074e0089803",
        transformation="Center portrait crop, 540x720 resize, translucent center text overlay.",
    )


def _multiline_sample(clean: Image.Image) -> dict:
    region = {"x0": 50, "y0": 520, "x1": 490, "y1": 690}
    image = clean.convert("RGBA")
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((50, 520, 489, 689), radius=14, fill=(10, 14, 22, 158))
    font = ImageFont.load_default(size=25)
    draw.text((78, 545), "WATERMARK REMOVER", font=font, fill=(255, 255, 255, 238))
    draw.text((78, 592), "LOCAL PROCESSING", font=font, fill=(214, 236, 228, 228))
    draw.text((78, 639), "2026 / MOBILE", font=font, fill=(255, 220, 170, 228))
    return _save_sample(
        "real-night-multiline",
        Image.alpha_composite(image, overlay).convert("RGB"),
        region,
        expected_low_contrast=False,
        source_file="../image_complexity/nasa-earth-iss045e013851.jpg",
        source_sha256="cf7b480745b578ced3c8913761228fbff6660caf35b8301f7c232791ff504169",
        source_record="https://images.nasa.gov/details/iss045e013851",
        transformation="Portrait crop, 540x720 resize, opaque multi-line lower panel overlay.",
    )


def _save_sample(
    sample_id: str,
    image: Image.Image,
    region: dict[str, int],
    *,
    expected_low_contrast: bool,
    source_file: str,
    source_sha256: str,
    source_record: str,
    transformation: str,
) -> dict:
    filename = f"{sample_id}.png"
    path = ROOT / filename
    image.save(path, format="PNG", compress_level=9)
    coverage = (region["x1"] - region["x0"]) * (region["y1"] - region["y0"]) / (
        SIZE[0] * SIZE[1]
    )
    return {
        "id": sample_id,
        "file": filename,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_file": source_file,
        "source_sha256": source_sha256,
        "source_record": source_record,
        "usage_terms_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
        "attribution": "NASA source photograph with repository-generated overlay.",
        "provenance_note": (
            "The underlying photograph is a pinned NASA source already stored in the "
            "repository. The portrait crop and watermark overlay are deterministic."
        ),
        "transformation": transformation,
        "width": SIZE[0],
        "height": SIZE[1],
        "region": region,
        "expected_low_contrast": expected_low_contrast,
        "expected_large_selection": coverage >= 0.10,
        "review_required": False,
    }


if __name__ == "__main__":
    main()
