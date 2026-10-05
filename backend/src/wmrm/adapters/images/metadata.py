import hashlib
import warnings
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from wmrm.application.assets import AssetError

SUPPORTED_FORMATS = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}
ORIENTATION_TAG = 274


@dataclass(frozen=True, slots=True)
class ImageInspection:
    width: int
    height: int
    display_width: int
    display_height: int
    format: str
    mode: str
    frames: int
    animated: bool
    has_alpha: bool
    exif_orientation: int
    has_icc_profile: bool
    transform_id: str
    inspected_parts: tuple[str, ...]
    warnings: tuple[str, ...]


class ImageInspector:
    def __init__(self, max_dimension: int, max_pixels: int, max_frames: int) -> None:
        self.max_dimension = max_dimension
        self.max_pixels = max_pixels
        self.max_frames = max_frames

    def inspect(self, path: Path, asset_sha256: str, asset_kind: str) -> ImageInspection:
        expected_format = SUPPORTED_FORMATS.get(asset_kind)
        if expected_format is None:
            raise AssetError("ANALYSIS_NOT_AVAILABLE", "该文件不是受支持的图片格式。", 409)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    image_format = str(image.format or "").upper()
                    if image_format != expected_format:
                        raise AssetError(
                            "INVALID_IMAGE",
                            "图片内容与上传时识别的格式不一致。",
                            422,
                        )
                    width, height = image.size
                    if width <= 0 or height <= 0:
                        raise AssetError("INVALID_IMAGE", "图片尺寸无效。", 422)
                    if width > self.max_dimension or height > self.max_dimension:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            f"图片边长超过 {self.max_dimension} 像素限制。",
                            413,
                        )
                    if width * height > self.max_pixels:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            f"图片像素总数超过 {self.max_pixels} 限制。",
                            413,
                        )
                    frames = int(getattr(image, "n_frames", 1))
                    if frames > self.max_frames:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            f"动态图帧数超过 {self.max_frames} 帧限制。",
                            413,
                        )
                    orientation = _orientation(image)
                    display_width, display_height = (
                        (height, width) if orientation in {5, 6, 7, 8} else (width, height)
                    )
                    mode = str(image.mode)
                    has_alpha = "A" in image.getbands() or "transparency" in image.info
                    has_icc_profile = bool(image.info.get("icc_profile"))
                    animated = bool(getattr(image, "is_animated", False) and frames > 1)
                with Image.open(path) as verifier:
                    verifier.verify()
        except AssetError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            RuntimeError,
            SyntaxError,
            ValueError,
        ) as exc:
            raise AssetError("INVALID_IMAGE", "文件不是可安全解析的图片。", 422) from exc

        transform_id = _transform_id(
            asset_sha256,
            width,
            height,
            display_width,
            display_height,
            orientation,
            frames,
        )
        inspected_parts = ["image:header", "image:dimensions"]
        if orientation != 1:
            inspected_parts.append("image:exif-orientation")
        if has_icc_profile:
            inspected_parts.append("image:icc-profile")
        if animated:
            inspected_parts.append("image:animation")
        messages = ["图片检查和蒙版预览不会修改原文件。"]
        if animated:
            messages.append("检测到动态图；当前蒙版仅适用于静态图片，暂不允许执行修复。")
        return ImageInspection(
            width=width,
            height=height,
            display_width=display_width,
            display_height=display_height,
            format=image_format,
            mode=mode,
            frames=frames,
            animated=animated,
            has_alpha=has_alpha,
            exif_orientation=orientation,
            has_icc_profile=has_icc_profile,
            transform_id=transform_id,
            inspected_parts=tuple(inspected_parts),
            warnings=tuple(messages),
        )


def _orientation(image: Image.Image) -> int:
    try:
        value = int(image.getexif().get(ORIENTATION_TAG, 1))
    except (AttributeError, TypeError, ValueError):
        return 1
    return value if 1 <= value <= 8 else 1


def _transform_id(asset_sha256: str, *parts: object) -> str:
    value = "|".join([asset_sha256, *(str(part) for part in parts)])
    return hashlib.sha256(value.encode()).hexdigest()[:24]
