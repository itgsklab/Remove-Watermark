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


@dataclass(frozen=True, slots=True)
class PhotoSceneAssessment:
    eligible: bool
    luminance_entropy: float
    quantized_color_count: int
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
        reasons = []
        if luminance_entropy < LUMINANCE_ENTROPY_THRESHOLD:
            reasons.append("全局亮度层次不足，图像更接近平面界面、文档或排版内容。")
        if quantized_color_count < QUANTIZED_COLOR_THRESHOLD:
            reasons.append("量化后的色彩种类不足，无法确认是自然照片场景。")
        eligible = not reasons
        if eligible:
            reasons.append("亮度层次和色彩多样性均达到保守的自然照片门槛。")
        return PhotoSceneAssessment(
            eligible=eligible,
            luminance_entropy=round(luminance_entropy, 4),
            quantized_color_count=quantized_color_count,
            reasons=tuple(reasons),
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
    }
