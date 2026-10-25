import hashlib
from collections.abc import Callable
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from wmrm.adapters.images.masks import rasterize_image_mask


def inpaint_image(
    source_path: Path,
    output_path: Path,
    regions: list[dict[str, Any]],
    radius: int,
    cancelled: Callable[[], bool] | None = None,
    protected_regions: list[dict[str, Any]] | None = None,
    polygons: list[dict[str, Any]] | None = None,
) -> dict[str, int | str]:
    should_cancel = cancelled or (lambda: False)
    _check_cancelled(should_cancel)

    with Image.open(source_path) as source:
        if int(getattr(source, "n_frames", 1)) != 1:
            raise ValueError("OpenCV 基础修复仅支持静态图片。")
        source.load()
        source_exif_present = bool(source.getexif())
        source_icc_profile_present = bool(source.info.get("icc_profile"))
        display = ImageOps.exif_transpose(source)
        has_alpha = "A" in display.getbands() or "transparency" in display.info
        normalized = display.convert("RGBA" if has_alpha else "RGB")

    original = np.asarray(normalized, dtype=np.uint8).copy()
    height, width = original.shape[:2]
    mask = rasterize_image_mask(width, height, regions, polygons, protected_regions)
    if not np.any(mask):
        raise ValueError("保护区不能覆盖全部蒙版。")

    _check_cancelled(should_cancel)
    repaired_rgb = cv2.inpaint(original[:, :, :3], mask, float(radius), cv2.INPAINT_TELEA)
    if original.shape[2] == 4:
        repaired_alpha = cv2.inpaint(original[:, :, 3], mask, float(radius), cv2.INPAINT_TELEA)
        repaired = np.dstack((repaired_rgb, repaired_alpha))
        output_mode = "RGBA"
    else:
        repaired = repaired_rgb
        output_mode = "RGB"
    _check_cancelled(should_cancel)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(repaired, mode=output_mode).save(output_path, format="PNG", compress_level=6)
    _check_cancelled(should_cancel)

    with Image.open(output_path) as result_image:
        if result_image.format != "PNG" or result_image.size != (width, height):
            raise ValueError("输出图片格式或尺寸校验失败。")
        output_exif_present = bool(result_image.getexif())
        output_icc_profile_present = bool(result_image.info.get("icc_profile"))
        if output_exif_present or output_icc_profile_present:
            raise ValueError("输出图片仍包含 EXIF 或 ICC 元数据。")
        result_image.load()
        decoded = np.asarray(result_image.convert(output_mode), dtype=np.uint8)

    changed = np.any(decoded != original, axis=2)
    outside_changed = int(np.count_nonzero(changed & (mask == 0)))
    if outside_changed:
        raise ValueError("输出图片在蒙版外发生了像素变化。")

    return {
        "removed_count": len(regions) + len(polygons or []),
        "polygon_count": len(polygons or []),
        "protected_count": len(protected_regions or []),
        "masked_pixels": int(np.count_nonzero(mask)),
        "changed_pixels": int(np.count_nonzero(changed)),
        "outside_changed_pixels": outside_changed,
        "engine": "opencv_telea",
        "radius": radius,
        "output_format": "PNG",
        "dimensions_match": True,
        "source_exif_present": source_exif_present,
        "source_icc_profile_present": source_icc_profile_present,
        "output_exif_present": output_exif_present,
        "output_icc_profile_present": output_icc_profile_present,
        "metadata_verified_clean": True,
        "width": width,
        "height": height,
        "size_bytes": output_path.stat().st_size,
        "sha256": _sha256(output_path),
    }


def _check_cancelled(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise CancelledError("任务已取消。")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
