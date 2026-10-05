import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import PIL
from PIL import Image, ImageDraw, ImageFont

from wmrm.adapters.images.complexity import ImageComplexityInspector
from wmrm.adapters.images.inpaint import inpaint_image
from wmrm.adapters.images.selection_risk import (
    LARGE_SELECTION_THRESHOLD,
    ImageSelectionRiskInspector,
)
from wmrm.benchmarks.image_quality import calculate_metrics

WIDTH = 360
HEIGHT = 480


@dataclass(frozen=True, slots=True)
class MobileBenchmarkCase:
    case_id: str
    label: str
    watermark_style: str
    clean: np.ndarray
    watermarked: np.ndarray
    mask: np.ndarray
    regions: tuple[dict[str, float], ...]
    expected_risk: str
    expected_low_contrast: bool


def generate_mobile_cases(seed: int = 20261005) -> list[MobileBenchmarkCase]:
    rng = np.random.default_rng(seed)
    return [
        _corner_case(),
        _translucent_case(rng),
        _multiline_case(),
    ]


def run_mobile_benchmark(
    output_dir: Path,
    *,
    radius: int = 3,
    seed: int = 20261005,
    report_json: Path | None = None,
    report_markdown: Path | None = None,
) -> dict:
    if not 1 <= radius <= 10:
        raise ValueError("Benchmark radius must be between 1 and 10 pixels.")
    output_dir.mkdir(parents=True, exist_ok=True)
    inspector = ImageComplexityInspector()
    selection_inspector = ImageSelectionRiskInspector()
    results = []
    for case in generate_mobile_cases(seed):
        case_dir = output_dir / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        clean_path = case_dir / "clean.png"
        input_path = case_dir / "watermarked.png"
        mask_path = case_dir / "mask.png"
        result_path = case_dir / "result.png"
        Image.fromarray(case.clean).save(clean_path)
        Image.fromarray(case.watermarked).save(input_path)
        Image.fromarray(case.mask.astype(np.uint8) * 255).save(mask_path)
        processing = inpaint_image(
            input_path, result_path, list(case.regions), radius
        )
        with Image.open(result_path) as result_image:
            repaired = np.asarray(result_image.convert("RGB"), dtype=np.uint8)
        complexity = inspector.inspect(
            input_path, [SimpleNamespace(**region) for region in case.regions]
        )
        selection_risk = selection_inspector.inspect(
            input_path, [SimpleNamespace(**region) for region in case.regions]
        )
        actual_risk = max(
            (item.risk for item in complexity),
            key={"low": 0, "review": 1, "high": 2}.__getitem__,
        )
        metrics = calculate_metrics(
            case.clean, case.watermarked, repaired, case.mask
        )
        quality_outcome = (
            "improved" if metrics["improvement_percent"] > 0 else "degraded"
        )
        checks = {
            "risk_matches": actual_risk == case.expected_risk,
            "outside_pixels_preserved": metrics["outside_mae"] == 0,
            "all_regions_processed": processing["removed_count"]
            == len(case.regions),
            "low_contrast_matches": any(
                item.low_contrast for item in selection_risk
            )
            == case.expected_low_contrast,
        }
        results.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "watermark_style": case.watermark_style,
                "expected_risk": case.expected_risk,
                "actual_risk": actual_risk,
                "expected_low_contrast": case.expected_low_contrast,
                "checks": checks,
                "artifacts": {
                    "clean": f"{case.case_id}/clean.png",
                    "watermarked": f"{case.case_id}/watermarked.png",
                    "mask": f"{case.case_id}/mask.png",
                    "result": f"{case.case_id}/result.png",
                },
                "regions": list(case.regions),
                "mask_fraction": round(float(case.mask.mean()), 4),
                "metrics": metrics,
                "quality_outcome": quality_outcome,
                "complexity": [
                    {
                        "risk": item.risk,
                        "texture": item.texture_score,
                        "edge_density": item.edge_density,
                        "periodicity": item.periodicity_score,
                        "structure": item.structure_score,
                        "reasons": item.reasons,
                    }
                    for item in complexity
                ],
                "selection_risk": {
                    "large_selection": float(case.mask.mean())
                    >= LARGE_SELECTION_THRESHOLD,
                    "regions": [
                        {
                            "mean_luma_delta": item.mean_luma_delta,
                            "low_contrast": item.low_contrast,
                            "reason": item.reason,
                        }
                        for item in selection_risk
                    ],
                },
                "processing": processing,
            }
        )

    failed_checks = sum(
        not passed
        for item in results
        for passed in item["checks"].values()
    )
    payload = {
        "schema_version": 1,
        "benchmark": "wmrm-mobile-watermark-inpainting",
        "provenance": (
            "All portrait images and watermark overlays are generated deterministically "
            "by this repository; no external assets or user data are used."
        ),
        "seed": seed,
        "radius": radius,
        "dimensions": {"width": WIDTH, "height": HEIGHT},
        "versions": {
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "pillow": PIL.__version__,
        },
        "summary": {
            "scenario_count": len(results),
            "failed_check_count": failed_checks,
            "outside_pixel_integrity_cases": sum(
                item["checks"]["outside_pixels_preserved"] for item in results
            ),
            "grades": {
                grade: sum(item["metrics"]["grade"] == grade for item in results)
                for grade in ("excellent", "good", "review", "poor")
            },
            "degraded_case_count": sum(
                item["quality_outcome"] == "degraded" for item in results
            ),
            "status": "pass" if failed_checks == 0 else "review",
            "recommendation": (
                "Keep automatic OpenCV use limited to small masks on smooth backgrounds. "
                "Require before/after review for translucent marks and large structured "
                "overlays because removal can damage more pixels than the watermark changed."
            ),
        },
        "cases": results,
    }
    json_path = report_json or output_dir / "report.json"
    markdown_path = report_markdown or output_dir / "report.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _corner_case() -> MobileBenchmarkCase:
    clean = _sky_photo()
    region = {"x0": 242, "y0": 22, "x1": 348, "y1": 60}
    watermarked = _overlay(
        clean,
        region,
        lambda draw: (
            draw.rounded_rectangle((242, 22, 347, 59), radius=9, fill=(8, 16, 28, 150)),
            draw.text(
                (253, 31),
                "@sample",
                font=ImageFont.load_default(size=15),
                fill=(255, 255, 255, 235),
            ),
        ),
    )
    return _case(
        "corner-small",
        "右上角小水印",
        "small_corner_badge",
        clean,
        watermarked,
        (region,),
        "low",
        False,
    )


def _translucent_case(rng: np.random.Generator) -> MobileBenchmarkCase:
    clean = _textured_photo(rng)
    region = {"x0": 55, "y0": 205, "x1": 305, "y1": 275}
    watermarked = _overlay(
        clean,
        region,
        lambda draw: draw.text(
            (88, 220),
            "SAMPLE",
            font=ImageFont.load_default(size=42),
            fill=(255, 255, 255, 105),
            stroke_width=1,
            stroke_fill=(20, 25, 30, 60),
        ),
    )
    return _case(
        "translucent-center",
        "中央半透明水印",
        "translucent_text",
        clean,
        watermarked,
        (region,),
        "review",
        True,
    )


def _multiline_case() -> MobileBenchmarkCase:
    clean = _architecture_photo()
    region = {"x0": 35, "y0": 330, "x1": 325, "y1": 444}

    def draw_multiline(draw: ImageDraw.ImageDraw) -> None:
        draw.rounded_rectangle((35, 330, 324, 443), radius=12, fill=(10, 14, 22, 145))
        font = ImageFont.load_default(size=19)
        draw.text((55, 345), "WATERMARK REMOVER", font=font, fill=(255, 255, 255, 235))
        draw.text((55, 376), "LOCAL PROCESSING", font=font, fill=(214, 236, 228, 225))
        draw.text((55, 407), "2026 / MOBILE", font=font, fill=(255, 220, 170, 225))

    watermarked = _overlay(clean, region, draw_multiline)
    return _case(
        "multiline-overlay",
        "底部多行文字覆盖",
        "multiline_panel",
        clean,
        watermarked,
        (region,),
        "high",
        False,
    )


def _case(
    case_id: str,
    label: str,
    style: str,
    clean: np.ndarray,
    watermarked: np.ndarray,
    regions: tuple[dict[str, float], ...],
    expected_risk: str,
    expected_low_contrast: bool,
) -> MobileBenchmarkCase:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    for region in regions:
        mask[
            int(region["y0"]):int(region["y1"]),
            int(region["x0"]):int(region["x1"]),
        ] = True
    if np.any(clean[~mask] != watermarked[~mask]):
        raise ValueError(f"Watermark escaped declared regions for {case_id}.")
    return MobileBenchmarkCase(
        case_id=case_id,
        label=label,
        watermark_style=style,
        clean=clean,
        watermarked=watermarked,
        mask=mask,
        regions=regions,
        expected_risk=expected_risk,
        expected_low_contrast=expected_low_contrast,
    )


def _overlay(clean: np.ndarray, region: dict[str, float], painter) -> np.ndarray:
    base = Image.fromarray(clean).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    painter(ImageDraw.Draw(overlay))
    result = np.asarray(Image.alpha_composite(base, overlay).convert("RGB"), dtype=np.uint8)
    x0, y0, x1, y1 = (int(region[key]) for key in ("x0", "y0", "x1", "y1"))
    allowed = np.zeros((HEIGHT, WIDTH), dtype=bool)
    allowed[y0:y1, x0:x1] = True
    if np.any(result[~allowed] != clean[~allowed]):
        raise ValueError("Overlay painter wrote outside its declared region.")
    return result


def _sky_photo() -> np.ndarray:
    y = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None]
    red = np.broadcast_to(65 + 120 * y, (HEIGHT, WIDTH))
    green = np.broadcast_to(125 + 85 * y, (HEIGHT, WIDTH))
    blue = np.broadcast_to(205 - 35 * y, (HEIGHT, WIDTH))
    image = np.stack((red, green, blue), axis=2).clip(0, 255).astype(np.uint8)
    canvas = Image.fromarray(image)
    draw = ImageDraw.Draw(canvas)
    draw.polygon(
        [(0, 365), (85, 280), (170, 360), (250, 300), (360, 375), (360, 480), (0, 480)],
        fill=(54, 92, 72),
    )
    draw.ellipse((42, 80, 104, 142), fill=(246, 220, 155))
    return np.asarray(canvas, dtype=np.uint8)


def _textured_photo(rng: np.random.Generator) -> np.ndarray:
    noise = rng.integers(0, 256, (HEIGHT, WIDTH, 3), dtype=np.uint8)
    smooth = cv2.GaussianBlur(noise, (0, 0), 3)
    detail = cv2.addWeighted(noise, 0.35, smooth, 0.65, 0)
    y = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None, None]
    tint = np.array([48, 92, 118], dtype=np.float32)[None, None, :]
    warm = np.array([190, 142, 92], dtype=np.float32)[None, None, :]
    gradient = np.broadcast_to(tint * (1 - y) + warm * y, (HEIGHT, WIDTH, 3))
    return cv2.addWeighted(detail, 0.6, gradient.astype(np.uint8), 0.4, 0)


def _architecture_photo() -> np.ndarray:
    image = Image.new("RGB", (WIDTH, HEIGHT), (213, 207, 191))
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 55, 332, 465), fill=(178, 165, 143), outline=(52, 62, 68), width=5)
    for x in range(52, 320, 58):
        draw.line((x, 60, x, 460), fill=(62, 74, 78), width=5)
    for y in range(90, 450, 62):
        draw.line((32, y, 328, y), fill=(80, 69, 58), width=4)
    for x in range(60, 300, 58):
        for y in range(105, 420, 62):
            draw.rectangle((x, y, x + 30, y + 36), fill=(83, 130, 145))
    return np.asarray(image, dtype=np.uint8)


def _markdown(payload: dict) -> str:
    rows = [
        "| Scenario | Mask | Risk | Low contrast | Large | MAE | Improvement | "
        "Outcome | Grade | Checks |",
        "|---|---:|---|---|---|---:|---:|---|---|---|",
    ]
    for item in payload["cases"]:
        checks = "pass" if all(item["checks"].values()) else "review"
        metrics = item["metrics"]
        rows.append(
            f"| {item['label']} | {item['mask_fraction'] * 100:.2f}% | "
            f"{item['actual_risk']} | "
            f"{str(item['selection_risk']['regions'][0]['low_contrast']).lower()} | "
            f"{str(item['selection_risk']['large_selection']).lower()} | "
            f"{metrics['masked_mae']:.2f} | {metrics['improvement_percent']:.2f}% | "
            f"{item['quality_outcome']} | {metrics['grade']} | {checks} |"
        )
    summary = payload["summary"]
    return "\n".join(
        [
            "# Mobile watermark benchmark",
            "",
            payload["provenance"],
            "",
            f"Status: **{summary['status']}** · Scenarios: {summary['scenario_count']} · "
            f"Failed checks: {summary['failed_check_count']} · "
            f"Outside-mask integrity: {summary['outside_pixel_integrity_cases']}/"
            f"{summary['scenario_count']}",
            "",
            *rows,
            "",
            "The benchmark covers a small corner badge, translucent center text and a "
            "multi-line lower overlay on portrait images. Quality grades describe the "
            "OpenCV baseline and are not perceptual guarantees.",
            "",
            summary["recommendation"],
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the mobile watermark benchmark.")
    parser.add_argument("--output", type=Path, default=Path("work/mobile-watermark"))
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--radius", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = run_mobile_benchmark(
        args.output,
        radius=args.radius,
        seed=args.seed,
        report_json=args.report_json,
        report_markdown=args.report_md,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 1 if args.strict and report["summary"]["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
