from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

LOW_CONTRAST_THRESHOLD = 0.04
LARGE_SELECTION_THRESHOLD = 0.10


@dataclass(frozen=True, slots=True)
class ImageRegionSelectionRisk:
    region_index: int
    mean_luma_delta: float
    low_contrast: bool
    reason: str


class ImageSelectionRiskInspector:
    """Estimate whether a selected mark is faint relative to its nearby context."""

    def inspect(
        self, path: Path, regions: list[object]
    ) -> list[ImageRegionSelectionRisk]:
        with Image.open(path) as source:
            image = np.asarray(ImageOps.exif_transpose(source).convert("RGB"))
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        return [
            self._inspect_region(gray, index, region)
            for index, region in enumerate(regions)
        ]

    @staticmethod
    def _inspect_region(
        gray: np.ndarray, region_index: int, region: object
    ) -> ImageRegionSelectionRisk:
        height, width = gray.shape
        x0 = max(0, int(np.floor(region.x0)))
        y0 = max(0, int(np.floor(region.y0)))
        x1 = min(width, int(np.ceil(region.x1)))
        y1 = min(height, int(np.ceil(region.y1)))
        padding = max(16, round(max(x1 - x0, y1 - y0) * 0.4))
        area_x0 = max(0, x0 - padding)
        area_y0 = max(0, y0 - padding)
        area_x1 = min(width, x1 + padding)
        area_y1 = min(height, y1 + padding)
        local = gray[area_y0:area_y1, area_x0:area_x1]
        context = np.ones(local.shape, dtype=bool)
        context[y0 - area_y0:y1 - area_y0, x0 - area_x0:x1 - area_x0] = False
        selected = gray[y0:y1, x0:x1]
        if selected.size == 0 or not np.any(context):
            delta = 0.0
        else:
            delta = abs(float(selected.mean()) - float(local[context].mean())) / 255
        rounded = round(delta, 4)
        low_contrast = rounded < LOW_CONTRAST_THRESHOLD
        reason = (
            "选区与周围平均亮度接近，可能是半透明或低对比度水印；"
            "局部修复可能比保留原图造成更明显的变化。"
            if low_contrast
            else "选区与周围亮度差异明显，未触发低对比度水印提示。"
        )
        return ImageRegionSelectionRisk(
            region_index=region_index,
            mean_luma_delta=rounded,
            low_contrast=low_contrast,
            reason=reason,
        )
