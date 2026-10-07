from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol

from wmrm.adapters.images.selection_risk import LARGE_SELECTION_THRESHOLD


class SelectionRisk(Protocol):
    low_contrast: bool


@dataclass(frozen=True, slots=True)
class ImagePlanWarning:
    code: str
    message: str
    requires_acknowledgement: bool = True


def build_image_plan_warnings(
    coverage_ratio: float,
    selection_regions: Iterable[SelectionRisk],
    complexity_level: Literal["low", "review", "high"],
) -> list[ImagePlanWarning]:
    warnings = [
        ImagePlanWarning(
            code="IMAGE_OUTPUT_PNG",
            message="结果将保存为无损 PNG，并移除 EXIF、ICC 等原始元数据。",
            requires_acknowledgement=False,
        )
    ]
    if coverage_ratio > 0.25:
        warnings.append(
            ImagePlanWarning(
                code="IMAGE_MASK_OVER_25_PERCENT",
                message="蒙版覆盖超过图片面积的 25%，修复可能明显改变主体内容。",
            )
        )
    elif coverage_ratio >= LARGE_SELECTION_THRESHOLD:
        warnings.append(
            ImagePlanWarning(
                code="IMAGE_MASK_OVER_10_PERCENT",
                message="蒙版覆盖达到图片面积的 10%；大选区修复必须逐图检查前后对比。",
            )
        )
    if any(item.low_contrast for item in selection_regions):
        warnings.append(
            ImagePlanWarning(
                code="IMAGE_LOW_CONTRAST_SELECTION",
                message=(
                    "选区与周围亮度接近，可能是半透明或低对比度水印；"
                    "基准中此类修复可能比原水印造成更大失真。"
                ),
            )
        )
    if complexity_level == "high":
        warnings.append(
            ImagePlanWarning(
                code="IMAGE_COMPLEXITY_HIGH",
                message=(
                    "蒙版周围包含周期纹理、密集细节或贯穿结构线，"
                    "OpenCV 修复可能产生明显伪影。"
                ),
            )
        )
    elif complexity_level == "review":
        warnings.append(
            ImagePlanWarning(
                code="IMAGE_COMPLEXITY_REVIEW",
                message="蒙版周围包含一定纹理，处理完成后请放大检查边界。",
                requires_acknowledgement=False,
            )
        )
    return warnings
