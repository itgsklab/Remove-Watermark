from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT.parent
IMAGE_ROOT = FIXTURE_ROOT / "image_complexity"
MOBILE_ROOT = FIXTURE_ROOT / "mobile_selection_corpus"


def main() -> None:
    generated = [
        _pair(
            "photo-horizon",
            "natural_scene",
            "nasa-iss074e0089803",
            _horizon_scene(),
            _corner_badge,
        ),
        _pair(
            "photo-night",
            "natural_scene",
            "nasa-iss045e013851",
            _night_scene(),
            _top_preview,
        ),
        _pair("dashboard", "ordinary_ui", "generated-dashboard", _dashboard_scene(), _center_demo),
        _pair("document", "document", "generated-document", _document_scene(), _diagonal_draft),
        _pair(
            "code-editor",
            "ordinary_ui",
            "generated-code-editor",
            _code_scene(),
            _internal_badge,
        ),
        _pair("poster", "typography", "generated-poster", _poster_scene(), _poster_sample),
        _pair(
            "mobile-feed",
            "ordinary_ui",
            "generated-mobile-feed",
            _mobile_feed_scene(),
            _creator_mark,
        ),
    ]
    manifest = {
        "schema_version": 1,
        "description": (
            "Reviewed paired positive and negative images for the watermark-localization "
            "contract. Generated pairs share the same deterministic clean scene so false "
            "positives and watermark sensitivity can be compared directly."
        ),
        "samples": [*_existing_samples(), *(item for pair in generated for item in pair)],
    }
    (ROOT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_contract_predictions(manifest)


def _existing_samples() -> list[dict]:
    return [
        _existing(
            "real-horizon-corner",
            "../mobile_selection_corpus/real-horizon-corner.png",
            MOBILE_ROOT / "real-horizon-corner.png",
            [{"x0": 400, "y0": 30, "x1": 520, "y1": 74, "label": "watermark"}],
            "natural_scene",
            "nasa-iss074e0089803",
            "NASA source photograph with repository-generated opaque corner overlay.",
        ),
        _existing(
            "real-horizon-translucent",
            "../mobile_selection_corpus/real-horizon-translucent.png",
            MOBILE_ROOT / "real-horizon-translucent.png",
            [{"x0": 125, "y0": 157, "x1": 326, "y1": 197, "label": "watermark"}],
            "natural_scene",
            "nasa-iss074e0089803",
            (
                "NASA source photograph with repository-generated translucent center text. "
                "Visible glyph bounds come from the deterministic Pillow textbbox used by the "
                "fixture builder; the wider mobile-risk selection is not reused as localization "
                "truth."
            ),
        ),
        _existing(
            "real-night-multiline",
            "../mobile_selection_corpus/real-night-multiline.png",
            MOBILE_ROOT / "real-night-multiline.png",
            [{"x0": 50, "y0": 520, "x1": 490, "y1": 690, "label": "watermark"}],
            "natural_scene",
            "nasa-iss045e013851",
            "NASA source photograph with repository-generated opaque multiline overlay.",
        ),
        _existing(
            "clean-horizon-negative",
            "../image_complexity/nasa-earth-iss074e0089803.jpg",
            IMAGE_ROOT / "nasa-earth-iss074e0089803.jpg",
            [],
            "natural_scene",
            "nasa-iss074e0089803",
            "Unmodified pinned NASA source photograph used as a negative localization sample.",
        ),
        _existing(
            "clean-night-negative",
            "../image_complexity/nasa-earth-iss045e013851.jpg",
            IMAGE_ROOT / "nasa-earth-iss045e013851.jpg",
            [],
            "natural_scene",
            "nasa-iss045e013851",
            "Unmodified pinned NASA source photograph used as a negative localization sample.",
        ),
        _existing(
            "clean-project-ui-negative",
            "../image_complexity/project-home-desktop.png",
            IMAGE_ROOT / "project-home-desktop.png",
            [],
            "ordinary_ui",
            "project-home-ui",
            (
                "Repository-generated Watermark Remover home-page screenshot with no user data "
                "or watermark, used to measure text-heavy UI false positives."
            ),
        ),
    ]


def _existing(
    sample_id: str,
    relative: str,
    path: Path,
    expected: list[dict],
    scene_kind: str,
    source_group: str,
    provenance: str,
) -> dict:
    with Image.open(path) as image:
        width, height = image.size
    return {
        "id": sample_id,
        "file": relative,
        "sha256": _sha256(path),
        "width": width,
        "height": height,
        "expected_regions": expected,
        "scene_kind": scene_kind,
        "source_group": source_group,
        "pair_id": None,
        "provenance": provenance,
        "review_required": False,
    }


def _pair(
    sample_id: str,
    scene_kind: str,
    source_group: str,
    clean: Image.Image,
    painter,
) -> tuple[dict, dict]:
    clean_name = f"paired-{sample_id}-clean.png"
    marked_name = f"paired-{sample_id}-watermark.png"
    clean_path = ROOT / clean_name
    marked_path = ROOT / marked_name
    clean.save(clean_path, format="PNG", compress_level=9)
    marked, region, description = painter(clean)
    marked.save(marked_path, format="PNG", compress_level=9)
    common = {
        "width": clean.width,
        "height": clean.height,
        "scene_kind": scene_kind,
        "source_group": source_group,
        "pair_id": sample_id,
        "review_required": False,
    }
    negative = {
        "id": f"paired-{sample_id}-negative",
        "file": clean_name,
        "sha256": _sha256(clean_path),
        "expected_regions": [],
        "provenance": (
            "Deterministic repository-generated clean scene with no user or third-party data."
        ),
        **common,
    }
    positive = {
        "id": f"paired-{sample_id}-positive",
        "file": marked_name,
        "sha256": _sha256(marked_path),
        "expected_regions": [{**region, "label": "watermark"}],
        "provenance": f"Paired clean scene with deterministic repository-generated {description}.",
        **common,
    }
    return negative, positive


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def _canvas(size: tuple[int, int], color: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", size, color)
    return image, ImageDraw.Draw(image)


def _horizon_scene() -> Image.Image:
    with Image.open(IMAGE_ROOT / "nasa-earth-iss074e0089803.jpg") as source:
        return (
            source.convert("RGB")
            .crop((180, 80, 1100, 700))
            .resize((720, 480), Image.Resampling.LANCZOS)
        )


def _night_scene() -> Image.Image:
    with Image.open(IMAGE_ROOT / "nasa-earth-iss045e013851.jpg") as source:
        return (
            source.convert("RGB")
            .crop((120, 80, 1160, 800))
            .resize((720, 480), Image.Resampling.LANCZOS)
        )


def _dashboard_scene() -> Image.Image:
    image, draw = _canvas((720, 540), "#f3f6f4")
    draw.rectangle((0, 0, 155, 540), fill="#17342d")
    draw.text((28, 32), "LOCAL TOOLS", font=_font(22), fill="#ffffff")
    for index, label in enumerate(("Overview", "Files", "Jobs", "Settings")):
        y = 104 + index * 48
        if index == 0:
            draw.rounded_rectangle((18, y - 8, 137, y + 28), radius=8, fill="#2e574d")
        draw.text((32, y), label, font=_font(16), fill="#e8f2ef")
    draw.text((190, 38), "Processing overview", font=_font(27), fill="#16352e")
    draw.text((190, 78), "Local tasks and storage", font=_font(15), fill="#64746f")
    for x, title, value in (
        (190, "Completed", "18"),
        (360, "Queued", "3"),
        (530, "Storage", "42%"),
    ):
        draw.rounded_rectangle((x, 120, x + 145, 225), radius=12, fill="#ffffff", outline="#d9e3df")
        draw.text((x + 18, 142), title, font=_font(15), fill="#65756f")
        draw.text((x + 18, 177), value, font=_font(28), fill="#173c33")
    draw.rounded_rectangle((190, 260, 675, 500), radius=12, fill="#ffffff", outline="#d9e3df")
    draw.text((215, 282), "Recent files", font=_font(19), fill="#173c33")
    for index, (name, state) in enumerate(
        (("report.pdf", "Done"), ("photo.png", "Ready"), ("notes.docx", "Queued"))
    ):
        y = 330 + index * 48
        draw.line((215, y + 34, 650, y + 34), fill="#e5ebe8", width=1)
        draw.text((215, y), name, font=_font(15), fill="#263b35")
        draw.text((575, y), state, font=_font(14), fill="#52766c")
    return image


def _document_scene() -> Image.Image:
    image, draw = _canvas((720, 540), "#d9dee3")
    draw.rectangle((105, 25, 615, 515), fill="#ffffff", outline="#c5cbd0")
    draw.text((145, 62), "PROJECT BRIEF", font=_font(28), fill="#1d2935")
    draw.text((145, 108), "October 2026", font=_font(14), fill="#65717c")
    draw.line((145, 140, 575, 140), fill="#cad1d7", width=2)
    draw.text((145, 168), "Objectives", font=_font(19), fill="#263746")
    body = (
        "Process files locally and keep the review flow clear.",
        "Support images, PDF documents and Word documents.",
        "Show every detected region before applying changes.",
    )
    for index, line in enumerate(body):
        y = 208 + index * 36
        draw.ellipse((148, y + 6, 154, y + 12), fill="#334b5d")
        draw.text((170, y), line, font=_font(14), fill="#3e4c58")
    draw.text((145, 350), "Delivery notes", font=_font(19), fill="#263746")
    for index, width in enumerate((410, 385, 425, 300)):
        y = 390 + index * 24
        draw.rounded_rectangle((145, y, 145 + width, y + 9), radius=4, fill="#dfe4e8")
    return image


def _code_scene() -> Image.Image:
    image, draw = _canvas((720, 540), "#111821")
    draw.rectangle((0, 0, 720, 42), fill="#202a35")
    draw.text((18, 12), "localizer.py", font=_font(15), fill="#dce5ed")
    draw.rectangle((0, 42, 150, 540), fill="#18212b")
    for index, name in enumerate(("src", "adapters", "images", "tests", "docs")):
        draw.text((20 + index * 4, 72 + index * 34), name, font=_font(14), fill="#9eb0bf")
    lines = (
        "def localize(image, prompt):",
        "    boxes = model.predict(image, prompt)",
        "    return validate_bounds(boxes)",
        "",
        "def validate_bounds(boxes):",
        "    for box in boxes:",
        "        if box.coverage > limit:",
        "            continue",
        "        yield box",
    )
    for index, line in enumerate(lines, start=1):
        y = 72 + (index - 1) * 34
        draw.text((172, y), f"{index:>2}", font=_font(14), fill="#566675")
        draw.text((210, y), line, font=_font(15), fill="#c7d5df")
    draw.rectangle((150, 500, 720, 540), fill="#19232e")
    draw.text(
        (172, 512), "Python 3.12     UTF-8     Local workspace", font=_font(13), fill="#91a4b4"
    )
    return image


def _poster_scene() -> Image.Image:
    image, draw = _canvas((720, 540), "#f5e8cd")
    draw.rectangle((34, 34, 686, 506), outline="#233e3a", width=3)
    draw.text((82, 78), "LOCAL", font=_font(72), fill="#193d38")
    draw.text((82, 158), "MADE SIMPLE", font=_font(53), fill="#193d38")
    draw.rectangle((82, 250, 638, 254), fill="#d06345")
    draw.text((82, 292), "FILES STAY ON THIS DEVICE", font=_font(24), fill="#3b514d")
    draw.text((82, 344), "Preview  /  Review  /  Export", font=_font(18), fill="#6a5548")
    draw.rounded_rectangle((82, 414, 262, 462), radius=8, fill="#193d38")
    draw.text((112, 428), "OPEN TOOL", font=_font(17), fill="#fff8e9")
    return image


def _mobile_feed_scene() -> Image.Image:
    image, draw = _canvas((540, 720), "#f7f5f1")
    draw.text((28, 24), "Discover", font=_font(28), fill="#222826")
    draw.rounded_rectangle((28, 72, 512, 112), radius=18, fill="#ebe8e2")
    draw.text((52, 84), "Search local projects", font=_font(15), fill="#777c79")
    colors = ("#b7d5cc", "#e7bd9d", "#9eb6cd", "#d8cea6")
    for index, color in enumerate(colors):
        col = index % 2
        row = index // 2
        x = 28 + col * 250
        y = 142 + row * 250
        draw.rounded_rectangle((x, y, x + 234, y + 185), radius=14, fill=color)
        draw.ellipse((x + 76, y + 38, x + 158, y + 120), fill="#ffffff80")
        draw.text((x + 8, y + 202), f"Collection {index + 1}", font=_font(16), fill="#2d3432")
        draw.text((x + 8, y + 226), "Saved locally", font=_font(13), fill="#707773")
    draw.rectangle((0, 660, 540, 720), fill="#ffffff")
    for x, label in ((52, "Home"), (220, "Files"), (392, "Profile")):
        draw.text((x, 682), label, font=_font(14), fill="#4c5552")
    return image


def _place_text(
    clean: Image.Image,
    text: str,
    font_size: int,
    xy: tuple[int, int],
    fill: tuple[int, int, int, int],
    *,
    stroke_width: int = 0,
    stroke_fill: tuple[int, int, int, int] | None = None,
    angle: float = 0,
) -> tuple[Image.Image, dict[str, int]]:
    raw = Image.new("RGBA", (clean.width, clean.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(raw)
    draw.text(
        (12, 12),
        text,
        font=_font(font_size),
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=stroke_fill,
    )
    glyph = raw.crop(raw.getbbox())
    if angle:
        glyph = glyph.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    alpha_box = glyph.getchannel("A").getbbox()
    glyph = glyph.crop(alpha_box)
    layer = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    layer.alpha_composite(glyph, xy)
    result = Image.alpha_composite(clean.convert("RGBA"), layer).convert("RGB")
    region = {"x0": xy[0], "y0": xy[1], "x1": xy[0] + glyph.width, "y1": xy[1] + glyph.height}
    return result, region


def _corner_badge(clean: Image.Image):
    layer = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    region = {"x0": 500, "y0": 390, "x1": 692, "y1": 448}
    draw.rounded_rectangle((500, 390, 691, 447), radius=12, fill=(10, 20, 27, 176))
    draw.text((520, 407), "@SAMPLE", font=_font(22), fill=(255, 255, 255, 244))
    return (
        Image.alpha_composite(clean.convert("RGBA"), layer).convert("RGB"),
        region,
        "opaque lower-right badge",
    )


def _top_preview(clean: Image.Image):
    image, region = _place_text(
        clean,
        "PREVIEW",
        44,
        (254, 36),
        (255, 255, 255, 92),
        stroke_width=1,
        stroke_fill=(12, 18, 30, 72),
    )
    return image, region, "translucent top-center text overlay"


def _center_demo(clean: Image.Image):
    image, region = _place_text(clean, "DEMO", 78, (238, 208), (28, 53, 46, 96), angle=12)
    return image, region, "rotated translucent center text overlay"


def _diagonal_draft(clean: Image.Image):
    image, region = _place_text(clean, "DRAFT", 82, (226, 205), (158, 50, 43, 86), angle=18)
    return image, region, "rotated translucent document text overlay"


def _internal_badge(clean: Image.Image):
    layer = Image.new("RGBA", clean.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    region = {"x0": 500, "y0": 62, "x1": 694, "y1": 110}
    draw.rounded_rectangle((500, 62, 693, 109), radius=8, fill=(190, 66, 48, 205))
    draw.text((518, 76), "INTERNAL", font=_font(20), fill=(255, 247, 238, 250))
    return (
        Image.alpha_composite(clean.convert("RGBA"), layer).convert("RGB"),
        region,
        "opaque top-right status badge",
    )


def _poster_sample(clean: Image.Image):
    image, region = _place_text(clean, "SAMPLE", 34, (446, 450), (176, 63, 43, 160))
    return image, region, "semi-transparent lower-right text overlay"


def _creator_mark(clean: Image.Image):
    image, region = _place_text(
        clean,
        "@CREATOR",
        26,
        (342, 624),
        (255, 255, 255, 225),
        stroke_width=2,
        stroke_fill=(20, 26, 24, 170),
    )
    return image, region, "outlined lower-right creator mark"


def _write_contract_predictions(manifest: dict) -> None:
    existing = {
        "real-horizon-corner": [
            {"x0": 398, "y0": 28, "x1": 522, "y1": 76, "label": "watermark", "confidence": 0.95}
        ],
        "real-horizon-translucent": [
            {"x0": 123, "y0": 153, "x1": 330, "y1": 204, "label": "watermark", "confidence": 0.9}
        ],
        "real-night-multiline": [
            {"x0": 45, "y0": 515, "x1": 495, "y1": 695, "label": "watermark", "confidence": 0.92}
        ],
    }
    rows = []
    for sample in manifest["samples"]:
        boxes = existing.get(sample["id"])
        if boxes is None:
            boxes = [{**box, "confidence": 0.95} for box in sample["expected_regions"]]
        rows.append({"sample_id": sample["id"], "boxes": boxes})
    predictions = {
        "schema_version": 1,
        "detector": {
            "id": "localization-contract-fixture",
            "model_id": None,
            "model_revision": None,
            "prompt": "watermark",
            "is_model_output": False,
            "note": (
                "Geometry fixture for testing the benchmark contract; not a model performance "
                "claim."
            ),
        },
        "predictions": rows,
    }
    (ROOT / "contract-predictions.json").write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
