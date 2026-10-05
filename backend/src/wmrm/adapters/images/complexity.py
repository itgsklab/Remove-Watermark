from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps

RiskLevel = Literal["low", "review", "high"]
MAX_SAMPLE_DIMENSION = 768
TEXTURE_SCORE_NORMALIZER = 30.0
STRUCTURE_SCORE_NORMALIZER = 0.04
PERIODICITY_HIGH_THRESHOLD = 0.8
PERIODICITY_MIN_TEXTURE = 0.1
STRUCTURE_HIGH_THRESHOLD = 0.30
EDGE_HIGH_THRESHOLD = 0.2
TEXTURE_REVIEW_THRESHOLD = 0.35
EDGE_REVIEW_THRESHOLD = 0.08


@dataclass(frozen=True, slots=True)
class RegionComplexity:
    region_index: int
    risk: RiskLevel
    texture_score: float
    edge_density: float
    periodicity_score: float
    structure_score: float
    context_pixels: int
    reasons: list[str]


class ImageComplexityInspector:
    """Estimate whether Telea inpainting is likely to need visual review.

    Features are measured in a ring around each mask so the watermark pixels inside
    the selected region do not influence the result. Scores are advisory and are
    calibrated against the repository's deterministic image benchmark.
    """

    def inspect(self, path: Path, regions: list[object]) -> list[RegionComplexity]:
        with Image.open(path) as source:
            image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
        return [
            self._inspect_region(image, index, region)
            for index, region in enumerate(regions)
        ]

    def _inspect_region(
        self, image: np.ndarray, region_index: int, region: object
    ) -> RegionComplexity:
        height, width = image.shape[:2]
        x0 = max(0, int(np.floor(region.x0)))
        y0 = max(0, int(np.floor(region.y0)))
        x1 = min(width, int(np.ceil(region.x1)))
        y1 = min(height, int(np.ceil(region.y1)))
        padding = max(16, round(max(x1 - x0, y1 - y0) * 0.4))
        area_x0 = max(0, x0 - padding)
        area_y0 = max(0, y0 - padding)
        area_x1 = min(width, x1 + padding)
        area_y1 = min(height, y1 + padding)
        inner_x0, inner_x1 = x0 - area_x0, x1 - area_x0
        inner_y0, inner_y1 = y0 - area_y0, y1 - area_y0

        gray = cv2.cvtColor(
            image[area_y0:area_y1, area_x0:area_x1], cv2.COLOR_RGB2GRAY
        )
        sample_scale = min(1.0, MAX_SAMPLE_DIMENSION / max(gray.shape))
        if sample_scale < 1.0:
            gray = cv2.resize(
                gray,
                (
                    max(1, round(gray.shape[1] * sample_scale)),
                    max(1, round(gray.shape[0] * sample_scale)),
                ),
                interpolation=cv2.INTER_AREA,
            )
            inner_x0 = round(inner_x0 * sample_scale)
            inner_x1 = round(inner_x1 * sample_scale)
            inner_y0 = round(inner_y0 * sample_scale)
            inner_y1 = round(inner_y1 * sample_scale)
        context = np.ones(gray.shape, dtype=np.uint8)
        context[inner_y0:inner_y1, inner_x0:inner_x1] = 0
        safe_context = cv2.erode(context, np.ones((5, 5), np.uint8)).astype(bool)
        context_pixels = int(safe_context.sum())
        if context_pixels == 0:
            return RegionComplexity(
                region_index=region_index,
                risk="review",
                texture_score=0.0,
                edge_density=0.0,
                periodicity_score=0.0,
                structure_score=0.0,
                context_pixels=0,
                reasons=["蒙版周围没有足够的上下文像素，无法可靠评估修复难度。"],
            )

        smoothed = cv2.GaussianBlur(gray, (3, 3), 0)
        laplacian = np.abs(cv2.Laplacian(smoothed, cv2.CV_32F))
        texture_score = min(
            1.0,
            float(np.percentile(laplacian[safe_context], 90))
            / TEXTURE_SCORE_NORMALIZER,
        )

        edges = cv2.Canny(gray, 50, 150)
        edge_density = float((edges[safe_context] > 0).mean())
        periodicity_score = self._context_periodicity(
            gray, inner_x0, inner_y0, inner_x1, inner_y1
        )
        structure_score = min(
            1.0,
            self._line_length_density(edges, safe_context)
            / STRUCTURE_SCORE_NORMALIZER,
        )

        reasons: list[str] = []
        if (
            periodicity_score >= PERIODICITY_HIGH_THRESHOLD
            and texture_score >= PERIODICITY_MIN_TEXTURE
        ):
            reasons.append("周围存在重复条纹或周期纹理，修复后可能出现断裂。")
        if structure_score >= STRUCTURE_HIGH_THRESHOLD:
            reasons.append("周围检测到较长结构边缘，可能穿过蒙版区域。")
        if edge_density >= EDGE_HIGH_THRESHOLD:
            reasons.append("周围细节和边缘密集，局部填充可能产生模糊或伪影。")

        high_risk = bool(reasons)
        if high_risk:
            risk: RiskLevel = "high"
        elif (
            texture_score >= TEXTURE_REVIEW_THRESHOLD
            or edge_density >= EDGE_REVIEW_THRESHOLD
        ):
            risk = "review"
            reasons.append("周围包含一定纹理，建议处理后放大检查边界。")
        else:
            risk = "low"
            reasons.append("周围背景较平滑，适合使用轻量 OpenCV 修复。")

        return RegionComplexity(
            region_index=region_index,
            risk=risk,
            texture_score=round(texture_score, 4),
            edge_density=round(edge_density, 4),
            periodicity_score=round(periodicity_score, 4),
            structure_score=round(structure_score, 4),
            context_pixels=context_pixels,
            reasons=reasons,
        )

    @staticmethod
    def _context_periodicity(
        gray: np.ndarray, x0: int, y0: int, x1: int, y1: int
    ) -> float:
        signals: list[np.ndarray] = []
        for strip in (gray[:y0], gray[y1:]):
            if strip.size:
                signals.extend((strip.mean(axis=0), strip.mean(axis=1)))
        for strip in (gray[y0:y1, :x0], gray[y0:y1, x1:]):
            if strip.size:
                signals.extend((strip.mean(axis=0), strip.mean(axis=1)))
        return max((ImageComplexityInspector._periodicity(item) for item in signals), default=0.0)

    @staticmethod
    def _periodicity(signal: np.ndarray) -> float:
        values = np.asarray(signal, dtype=np.float32)
        if values.size < 12:
            return 0.0
        kernel = max(3, (values.size // 8) | 1)
        trend = cv2.GaussianBlur(values.reshape(1, -1), (kernel, 1), 0).ravel()
        values = values - trend
        if float(np.dot(values, values)) < 1e-3:
            return 0.0
        correlations = []
        for lag in range(3, min(32, values.size // 2) + 1):
            left, right = values[:-lag], values[lag:]
            denominator = float(np.sqrt(np.dot(left, left) * np.dot(right, right)))
            if denominator > 1e-6:
                correlations.append(abs(float(np.dot(left, right))) / denominator)
        return min(1.0, max(correlations, default=0.0))

    @staticmethod
    def _line_length_density(edges: np.ndarray, context: np.ndarray) -> float:
        masked_edges = edges * context.astype(np.uint8)
        lines = cv2.HoughLinesP(
            masked_edges,
            1,
            np.pi / 180,
            threshold=18,
            minLineLength=max(10, round(min(edges.shape) * 0.18)),
            maxLineGap=7,
        )
        if lines is None:
            return 0.0
        total_length = sum(
            float(np.hypot(x1 - x0, y1 - y0))
            for x0, y0, x1, y1 in lines.reshape(-1, 4)
        )
        return total_length / max(1, int(context.sum()))
