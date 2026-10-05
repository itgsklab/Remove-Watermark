import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import PIL
from PIL import Image, ImageDraw

from wmrm.adapters.images.inpaint import inpaint_image

WIDTH = 256
HEIGHT = 160
MASK_BOX = (82, 56, 174, 104)


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    label: str
    clean: np.ndarray
    watermarked: np.ndarray
    mask: np.ndarray
    region: dict[str, float]


def generate_cases(seed: int = 20260928) -> list[BenchmarkCase]:
    rng = np.random.default_rng(seed)
    clean_images = [
        ("flat", "纯色背景", _flat()),
        ("gradient", "平滑渐变", _gradient()),
        ("stripes", "周期条纹", _stripes()),
        ("structure", "跨蒙版结构线", _structure()),
        ("texture", "固定随机纹理", _texture(rng)),
    ]
    return [_make_case(case_id, label, clean) for case_id, label, clean in clean_images]


def run_benchmark(
    output_dir: Path,
    *,
    radius: int = 3,
    seed: int = 20260928,
    report_json: Path | None = None,
    report_markdown: Path | None = None,
) -> dict:
    if not 1 <= radius <= 10:
        raise ValueError("Benchmark radius must be between 1 and 10 pixels.")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for case in generate_cases(seed):
        case_dir = output_dir / case.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        clean_path = case_dir / "clean.png"
        input_path = case_dir / "watermarked.png"
        mask_path = case_dir / "mask.png"
        result_path = case_dir / "result.png"
        Image.fromarray(case.clean).save(clean_path)
        Image.fromarray(case.watermarked).save(input_path)
        Image.fromarray(case.mask.astype(np.uint8) * 255).save(mask_path)
        processing = inpaint_image(input_path, result_path, [case.region], radius)
        with Image.open(result_path) as result_image:
            repaired = np.asarray(result_image.convert("RGB"), dtype=np.uint8)
        metrics = calculate_metrics(case.clean, case.watermarked, repaired, case.mask)
        results.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "artifacts": {
                    "clean": f"{case.case_id}/clean.png",
                    "watermarked": f"{case.case_id}/watermarked.png",
                    "mask": f"{case.case_id}/mask.png",
                    "result": f"{case.case_id}/result.png",
                },
                "metrics": metrics,
                "processing": processing,
            }
        )

    payload = {
        "schema_version": 1,
        "benchmark": "wmrm-synthetic-image-inpainting",
        "provenance": (
            "All images are generated procedurally by this repository; "
            "no external assets are used."
        ),
        "seed": seed,
        "radius": radius,
        "versions": {
            "opencv": cv2.__version__,
            "numpy": np.__version__,
            "pillow": PIL.__version__,
        },
        "summary": _summary(results),
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


def _make_case(case_id: str, label: str, clean: np.ndarray) -> BenchmarkCase:
    x0, y0, x1, y1 = MASK_BOX
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[y0:y1, x0:x1] = True
    base = Image.fromarray(clean).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=7, fill=(30, 25, 20, 132))
    draw.text((101, 75), "WMRM", fill=(255, 246, 226, 235), stroke_width=1)
    watermarked = np.asarray(Image.alpha_composite(base, overlay).convert("RGB"), dtype=np.uint8)
    return BenchmarkCase(
        case_id=case_id,
        label=label,
        clean=clean,
        watermarked=watermarked,
        mask=mask,
        region={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
    )


def _flat() -> np.ndarray:
    return np.full((HEIGHT, WIDTH, 3), (210, 195, 164), dtype=np.uint8)


def _gradient() -> np.ndarray:
    x = np.linspace(0, 1, WIDTH, dtype=np.float32)[None, :]
    y = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None]
    red = 55 + 150 * x + 20 * y
    green = 85 + 70 * x + 80 * y
    blue = 130 + 55 * x + 35 * y
    return np.stack(np.broadcast_arrays(red, green, blue), axis=2).clip(0, 255).astype(np.uint8)


def _stripes() -> np.ndarray:
    x = np.arange(WIDTH)[None, :]
    y = np.arange(HEIGHT)[:, None]
    wave = ((x // 9 + y // 13) % 2).astype(np.uint8)
    dark = np.array([42, 82, 96], dtype=np.uint8)
    light = np.array([224, 192, 126], dtype=np.uint8)
    return np.where(wave[:, :, None] == 1, light, dark)


def _structure() -> np.ndarray:
    image = Image.new("RGB", (WIDTH, HEIGHT), (230, 224, 207))
    draw = ImageDraw.Draw(image)
    draw.line((10, 135, 246, 20), fill=(38, 77, 65), width=8)
    draw.ellipse((68, 26, 188, 146), outline=(164, 64, 48), width=7)
    draw.line((128, 5, 128, 155), fill=(44, 55, 92), width=5)
    return np.asarray(image, dtype=np.uint8)


def _texture(rng: np.random.Generator) -> np.ndarray:
    noise = rng.integers(0, 256, size=(HEIGHT, WIDTH, 3), dtype=np.uint8)
    smooth = cv2.GaussianBlur(noise, (0, 0), 2.2)
    detail = cv2.addWeighted(noise, 0.35, smooth, 0.65, 0)
    return detail.astype(np.uint8)


def calculate_metrics(
    clean: np.ndarray,
    watermarked: np.ndarray,
    repaired: np.ndarray,
    mask: np.ndarray,
) -> dict[str, float | str]:
    input_error = np.abs(watermarked.astype(np.float32) - clean.astype(np.float32))
    result_error = np.abs(repaired.astype(np.float32) - clean.astype(np.float32))
    masked_mae = float(result_error[mask].mean())
    masked_rmse = float(np.sqrt(np.square(result_error[mask]).mean()))
    input_mae = float(input_error[mask].mean())
    outside_mae = float(result_error[~mask].mean())
    boundary = mask & ~cv2.erode(mask.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    boundary_mae = float(result_error[boundary].mean())
    changed = np.any(repaired != watermarked, axis=2)
    changed_mask_ratio = float(changed[mask].mean())
    improvement_percent = (
        float((input_mae - masked_mae) / input_mae * 100) if input_mae else 0.0
    )
    psnr = 99.0 if masked_rmse == 0 else float(20 * math.log10(255 / masked_rmse))
    return {
        "input_masked_mae": round(input_mae, 4),
        "masked_mae": round(masked_mae, 4),
        "masked_rmse": round(masked_rmse, 4),
        "masked_psnr_db": round(psnr, 4),
        "boundary_mae": round(boundary_mae, 4),
        "outside_mae": round(outside_mae, 4),
        "changed_mask_ratio": round(changed_mask_ratio, 4),
        "improvement_percent": round(improvement_percent, 2),
        "grade": _grade(masked_mae),
    }


def _grade(masked_mae: float) -> str:
    if masked_mae <= 5:
        return "excellent"
    if masked_mae <= 15:
        return "good"
    if masked_mae <= 30:
        return "review"
    return "poor"


def _summary(results: list[dict]) -> dict:
    metrics = [item["metrics"] for item in results]
    return {
        "scenario_count": len(results),
        "mean_masked_mae": round(
            sum(float(item["masked_mae"]) for item in metrics) / len(metrics), 4
        ),
        "mean_improvement_percent": round(
            sum(float(item["improvement_percent"]) for item in metrics) / len(metrics), 2
        ),
        "outside_pixel_integrity_cases": sum(
            float(item["outside_mae"]) == 0 for item in metrics
        ),
        "grades": {
            grade: sum(item["grade"] == grade for item in metrics)
            for grade in ("excellent", "good", "review", "poor")
        },
        "recommendation": (
            "Keep OpenCV Telea as the lightweight baseline for small masks on simple "
            "backgrounds; require visual review for structured or textured regions."
        ),
    }


def _markdown(payload: dict) -> str:
    rows = [
        "| Case | Mask MAE | PSNR dB | Boundary MAE | Improvement | Grade |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in payload["cases"]:
        metrics = item["metrics"]
        rows.append(
            f"| {item['label']} | {metrics['masked_mae']:.2f} | "
            f"{metrics['masked_psnr_db']:.2f} | {metrics['boundary_mae']:.2f} | "
            f"{metrics['improvement_percent']:.2f}% | {metrics['grade']} |"
        )
    summary = payload["summary"]
    versions = payload["versions"]
    return "\n".join(
        [
            "# OpenCV Telea synthetic benchmark",
            "",
            payload["provenance"],
            "",
            f"Seed: `{payload['seed']}` · Radius: `{payload['radius']}` · "
            f"OpenCV: `{versions['opencv']}` · NumPy: `{versions['numpy']}` · "
            f"Pillow: `{versions['pillow']}`",
            "",
            *rows,
            "",
            f"Mean masked MAE: **{summary['mean_masked_mae']:.2f}**. "
            f"Mean improvement: **{summary['mean_improvement_percent']:.2f}%**. "
            f"Outside-mask integrity: **{summary['outside_pixel_integrity_cases']}/"
            f"{summary['scenario_count']}** cases.",
            "",
            summary["recommendation"],
            "",
            "Grades are internal regression bands, not perceptual-quality guarantees. "
            "Inspect the generated images before changing product behavior.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the synthetic OpenCV inpainting benchmark.")
    parser.add_argument("--output", type=Path, default=Path("work/image-benchmark"))
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--radius", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--seed", type=int, default=20260928)
    args = parser.parse_args()
    report = run_benchmark(
        args.output,
        radius=args.radius,
        seed=args.seed,
        report_json=args.report_json,
        report_markdown=args.report_md,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
