from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wmrm.adapters.images.detection import LocalizationBox


@dataclass(frozen=True, slots=True)
class SegmentationMask:
    """Immutable row-major binary mask returned by an optional local refiner."""

    width: int
    height: int
    pixels: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Segmentation mask dimensions must be positive.")
        if len(self.pixels) != self.width * self.height:
            raise ValueError("Segmentation mask pixel count does not match its dimensions.")
        if any(value not in {0, 1} for value in self.pixels):
            raise ValueError("Segmentation mask pixels must be binary values 0 or 1.")

    @property
    def selected_pixels(self) -> int:
        return sum(self.pixels)


class WatermarkMaskRefiner(Protocol):
    """Model-independent boundary for box-guided, local-only mask refinement."""

    model_id: str
    model_revision: str
    runtime_metadata: dict[str, object]

    def refine(
        self,
        image_path: Path,
        boxes: tuple[LocalizationBox, ...],
    ) -> SegmentationMask: ...
