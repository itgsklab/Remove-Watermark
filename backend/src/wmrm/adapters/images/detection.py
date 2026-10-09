from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LocalizationBox:
    x0: float
    y0: float
    x1: float
    y1: float
    label: str
    confidence: float

    def __post_init__(self) -> None:
        coordinates = (self.x0, self.y0, self.x1, self.y1)
        if not all(math.isfinite(value) for value in coordinates):
            raise ValueError("Localization coordinates must be finite.")
        if self.x0 < 0 or self.y0 < 0 or self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("Localization box must have positive in-bounds geometry.")
        if not self.label.strip():
            raise ValueError("Localization label must not be empty.")
        if not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("Localization confidence must be between 0 and 1.")


class WatermarkLocalizer(Protocol):
    model_id: str
    model_revision: str

    def localize(self, image_path: Path, prompt: str) -> tuple[LocalizationBox, ...]: ...


def intersection_over_union(left: LocalizationBox, right: LocalizationBox) -> float:
    intersection_width = max(0.0, min(left.x1, right.x1) - max(left.x0, right.x0))
    intersection_height = max(0.0, min(left.y1, right.y1) - max(left.y0, right.y0))
    intersection = intersection_width * intersection_height
    left_area = (left.x1 - left.x0) * (left.y1 - left.y0)
    right_area = (right.x1 - right.x0) * (right.y1 - right.y0)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0
