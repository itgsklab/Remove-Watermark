import math
from typing import Any

import cv2
import numpy as np


def rasterize_image_mask(
    width: int,
    height: int,
    regions: list[Any],
    polygons: list[Any] | None = None,
    protected_regions: list[Any] | None = None,
) -> np.ndarray:
    """Build the exact uint8 mask used by preview and OpenCV processing."""
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        x0 = max(0, math.floor(float(_value(region, "x0"))))
        y0 = max(0, math.floor(float(_value(region, "y0"))))
        x1 = min(width, math.ceil(float(_value(region, "x1"))))
        y1 = min(height, math.ceil(float(_value(region, "y1"))))
        if x0 >= x1 or y0 >= y1:
            raise ValueError("蒙版区域为空或超出图片范围。")
        mask[y0:y1, x0:x1] = 255

    for polygon in polygons or []:
        points = np.asarray(
            [
                [round(float(_value(point, "x"))), round(float(_value(point, "y")))]
                for point in _value(polygon, "points")
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(mask, [points], 255)

    for region in protected_regions or []:
        x0 = max(0, math.floor(float(_value(region, "x0"))))
        y0 = max(0, math.floor(float(_value(region, "y0"))))
        x1 = min(width, math.ceil(float(_value(region, "x1"))))
        y1 = min(height, math.ceil(float(_value(region, "y1"))))
        if x0 >= x1 or y0 >= y1:
            raise ValueError("保护区域为空或超出图片范围。")
        mask[y0:y1, x0:x1] = 0
    return mask


def _value(item: Any, name: str) -> Any:
    return item[name] if isinstance(item, dict) else getattr(item, name)
