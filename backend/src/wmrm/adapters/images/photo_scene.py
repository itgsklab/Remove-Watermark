from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PIL import Image, ImageOps

from wmrm.adapters.images.detection import LocalizationBox

MAX_SAMPLE_DIMENSION = 256
LUMINANCE_ENTROPY_THRESHOLD = 4.5
QUANTIZED_COLOR_THRESHOLD = 128
COLOR_QUANTIZATION_STEP = 16
LUMINANCE_STANDARD_DEVIATION_THRESHOLD = 25.0
FLAT_GRADIENT_MAGNITUDE = 10.0
MAXIMUM_FLAT_GRADIENT_RATIO = 0.75
DARK_DETAIL_ENTROPY_THRESHOLD = 3.4
GRADIENT_ORIENTATION_MAGNITUDE = 20.0
GRADIENT_ORIENTATION_BIN_COUNT = 18
GRADIENT_ORIENTATION_ENTROPY_THRESHOLD = 3.9


@dataclass(frozen=True, slots=True)
class PhotoSceneAssessment:
    eligible: bool
    luminance_entropy: float
    quantized_color_count: int
    luminance_standard_deviation: float
    flat_gradient_ratio: float
    gradient_orientation_entropy: float
    matched_routes: tuple[str, ...]
    reasons: tuple[str, ...]


class PhotoSceneGate:
    """Conservatively identify photo-like pixels before optional VLM localization.

    The gate reads decoded pixels only. It does not inspect filenames, image metadata,
    model detections, text labels, or expected watermark coordinates.
    """

    def assess(self, path: Path) -> PhotoSceneAssessment:
        with Image.open(path) as source:
            image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
        height, width = image.shape[:2]
        scale = min(1.0, MAX_SAMPLE_DIMENSION / max(width, height))
        if scale < 1.0:
            image = cv2.resize(
                image,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        histogram = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
        probabilities = histogram[histogram > 0] / histogram.sum()
        luminance_entropy = float(-(probabilities * np.log2(probabilities)).sum())

        quantized = image.astype(np.uint16) // COLOR_QUANTIZATION_STEP
        color_ids = quantized[:, :, 0] * 256 + quantized[:, :, 1] * 16 + quantized[:, :, 2]
        quantized_color_count = int(np.unique(color_ids).size)
        luminance_standard_deviation = float(gray.std())
        gradient_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient_magnitude = cv2.magnitude(gradient_x, gradient_y)
        flat_gradient_ratio = float(np.mean(gradient_magnitude < FLAT_GRADIENT_MAGNITUDE))
        detailed = gradient_magnitude >= GRADIENT_ORIENTATION_MAGNITUDE
        if np.any(detailed):
            orientation = np.arctan2(gradient_y[detailed], gradient_x[detailed])
            orientation_histogram = np.histogram(
                orientation,
                bins=GRADIENT_ORIENTATION_BIN_COUNT,
                range=(-np.pi, np.pi),
            )[0].astype(np.float64)
            orientation_probabilities = (
                orientation_histogram[orientation_histogram > 0] / orientation_histogram.sum()
            )
            gradient_orientation_entropy = float(
                -(orientation_probabilities * np.log2(orientation_probabilities)).sum()
            )
        else:
            gradient_orientation_entropy = 0.0

        matched_routes = []
        if (
            luminance_entropy >= LUMINANCE_ENTROPY_THRESHOLD
            and quantized_color_count >= QUANTIZED_COLOR_THRESHOLD
        ):
            matched_routes.append("color-diversity")
        if (
            luminance_standard_deviation >= LUMINANCE_STANDARD_DEVIATION_THRESHOLD
            and flat_gradient_ratio <= MAXIMUM_FLAT_GRADIENT_RATIO
        ):
            matched_routes.append("continuous-tone")
        if (
            luminance_entropy >= DARK_DETAIL_ENTROPY_THRESHOLD
            and luminance_standard_deviation >= LUMINANCE_STANDARD_DEVIATION_THRESHOLD
            and gradient_orientation_entropy >= GRADIENT_ORIENTATION_ENTROPY_THRESHOLD
        ):
            matched_routes.append("distributed-detail")

        eligible = bool(matched_routes)
        reasons = (
            (
                "像素通过以下通用照片证据路径："
                f"{', '.join(matched_routes)}。"
            ),
        ) if eligible else (
            "色彩多样性、连续色调和分散方向细节均不足，无法确认是自然照片场景。",
        )
        return PhotoSceneAssessment(
            eligible=eligible,
            luminance_entropy=round(luminance_entropy, 4),
            quantized_color_count=quantized_color_count,
            luminance_standard_deviation=round(luminance_standard_deviation, 4),
            flat_gradient_ratio=round(flat_gradient_ratio, 6),
            gradient_orientation_entropy=round(gradient_orientation_entropy, 4),
            matched_routes=tuple(matched_routes),
            reasons=reasons,
        )


class WatermarkLocalizer(Protocol):
    model_id: str
    model_revision: str
    runtime_metadata: dict

    def localize(self, image_path: Path, prompt: str) -> tuple[LocalizationBox, ...]: ...


class PhotoGatedLocalizer:
    """Allow an optional localizer to run only on conservatively photo-like pixels."""

    def __init__(
        self, localizer: WatermarkLocalizer, *, gate: PhotoSceneGate | None = None
    ) -> None:
        self._localizer = localizer
        self._gate = gate or PhotoSceneGate()
        self.model_id = localizer.model_id
        self.model_revision = localizer.model_revision
        self.runtime_metadata = {
            "kind": "photo-gated-localizer",
            "localizer": localizer.runtime_metadata,
            "photo_scene_gate": photo_scene_gate_metadata(),
        }

    def localize(self, image_path: Path, prompt: str) -> tuple[LocalizationBox, ...]:
        if not self._gate.assess(image_path).eligible:
            return ()
        return self._localizer.localize(image_path, prompt)


def photo_scene_gate_metadata() -> dict[str, int | float]:
    return {
        "maximum_sample_dimension": MAX_SAMPLE_DIMENSION,
        "minimum_luminance_entropy": LUMINANCE_ENTROPY_THRESHOLD,
        "minimum_quantized_color_count": QUANTIZED_COLOR_THRESHOLD,
        "color_quantization_step": COLOR_QUANTIZATION_STEP,
        "minimum_luminance_standard_deviation": LUMINANCE_STANDARD_DEVIATION_THRESHOLD,
        "flat_gradient_magnitude": FLAT_GRADIENT_MAGNITUDE,
        "maximum_flat_gradient_ratio": MAXIMUM_FLAT_GRADIENT_RATIO,
        "minimum_dark_detail_entropy": DARK_DETAIL_ENTROPY_THRESHOLD,
        "gradient_orientation_magnitude": GRADIENT_ORIENTATION_MAGNITUDE,
        "gradient_orientation_bin_count": GRADIENT_ORIENTATION_BIN_COUNT,
        "minimum_gradient_orientation_entropy": GRADIENT_ORIENTATION_ENTROPY_THRESHOLD,
    }
