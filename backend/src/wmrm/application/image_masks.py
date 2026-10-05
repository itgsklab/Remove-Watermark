import json
import math
from dataclasses import asdict

from sqlalchemy.orm import Session

from wmrm.adapters.images.complexity import ImageComplexityInspector
from wmrm.adapters.images.selection_risk import (
    LARGE_SELECTION_THRESHOLD,
    ImageSelectionRiskInspector,
)
from wmrm.api.schemas import (
    AnalysisResponse,
    ImageComplexityResponse,
    ImageMaskPreviewResponse,
    ImageRegionComplexity,
    ImageRegionSelectionRisk,
    ImageSelectionRiskResponse,
    PreviewImageMasksRequest,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.persistence.database import AnalysisRecord


class ImageMaskService:
    def __init__(self, assets: AssetService) -> None:
        self.assets = assets
        self.complexity = ImageComplexityInspector()
        self.selection_risk = ImageSelectionRiskInspector()

    def preview(
        self, session: Session, request: PreviewImageMasksRequest
    ) -> ImageMaskPreviewResponse:
        asset = self.assets.get(session, request.asset_id)
        if asset.kind not in {"png", "jpeg", "webp"}:
            raise AssetError("IMAGE_MASK_NOT_AVAILABLE", "蒙版预览仅支持图片。", 409)
        record = session.get(AnalysisRecord, request.analysis_id)
        if record is None:
            raise AssetError("ANALYSIS_NOT_FOUND", "找不到该扫描结果。", 404)
        analysis = AnalysisResponse.model_validate(json.loads(record.result_json))
        metadata = analysis.image_metadata
        if analysis.preset != "image" or metadata is None:
            raise AssetError(
                "IMAGE_MASK_NOT_AVAILABLE", "蒙版预览需要图片检查结果。", 409
            )
        if analysis.asset_id != asset.id or analysis.asset_sha256 != asset.sha256:
            raise AssetError("PLAN_STALE", "图片检查结果已经失效，请重新检查。", 409)

        for region in request.regions:
            values = (region.x0, region.y0, region.x1, region.y1)
            if not all(math.isfinite(value) for value in values):
                raise AssetError("INVALID_MASK", "蒙版坐标必须是有限数字。", 422)
            if (
                region.transform_id != metadata.transform_id
                or region.x0 < 0
                or region.y0 < 0
                or region.x1 > metadata.display_width
                or region.y1 > metadata.display_height
                or region.x0 >= region.x1
                or region.y0 >= region.y1
            ):
                raise AssetError(
                    "PLAN_STALE",
                    "蒙版坐标或图片方向已经失效，请重新检查并框选。",
                    409,
                )

        covered_pixels = _rectangle_union_area(request.regions)
        coverage_ratio = covered_pixels / (
            metadata.display_width * metadata.display_height
        )
        assessments = self.complexity.inspect(self.assets.path_for(asset), request.regions)
        risk_order = {"low": 0, "review": 1, "high": 2}
        complexity_level = max(
            (item.risk for item in assessments), key=risk_order.__getitem__
        )
        complexity = ImageComplexityResponse(
            level=complexity_level,
            regions=[ImageRegionComplexity(**asdict(item)) for item in assessments],
        )
        selection_assessments = self.selection_risk.inspect(
            self.assets.path_for(asset), request.regions
        )
        large_selection = coverage_ratio >= LARGE_SELECTION_THRESHOLD
        low_contrast = any(item.low_contrast for item in selection_assessments)
        selection_risk = ImageSelectionRiskResponse(
            level="review" if large_selection or low_contrast else "normal",
            large_selection=large_selection,
            regions=[
                ImageRegionSelectionRisk(**asdict(item))
                for item in selection_assessments
            ],
        )
        requires_acknowledgement = (
            large_selection
            or low_contrast
            or metadata.animated
            or complexity_level == "high"
        )
        warnings = [
            "蒙版预览只验证计划修复的像素区域；创建处理任务后才会生成新图片。"
        ]
        if coverage_ratio > 0.25:
            warnings.append("蒙版覆盖超过图片面积的 25%，后续修复可能明显改变主体内容。")
        elif large_selection:
            warnings.append(
                "蒙版覆盖达到图片面积的 10%；移动端基准显示大选区需要逐图对比结果。"
            )
        if low_contrast:
            warnings.append(
                "检测到低对比度选区，可能包含半透明水印；"
                "OpenCV 修复可能比保留原图造成更明显的变化。"
            )
        if metadata.animated:
            warnings.append("动态图的逐帧蒙版尚未实现，当前草稿不能进入处理任务。")
        if complexity_level == "review":
            warnings.append("检测到一定背景纹理；处理完成后请放大检查蒙版边界。")
        elif complexity_level == "high":
            warnings.append("检测到周期纹理、密集细节或贯穿结构线，OpenCV 修复可能产生明显伪影。")
        return ImageMaskPreviewResponse(
            asset_id=asset.id,
            analysis_id=analysis.id,
            valid=True,
            executable=not metadata.animated,
            regions=request.regions,
            covered_pixels=covered_pixels,
            coverage_ratio=coverage_ratio,
            complexity=complexity,
            selection_risk=selection_risk,
            requires_acknowledgement=requires_acknowledgement,
            warnings=warnings,
        )


def _rectangle_union_area(regions) -> float:
    rectangles = [
        (
            math.floor(item.x0),
            math.floor(item.y0),
            math.ceil(item.x1),
            math.ceil(item.y1),
        )
        for item in regions
    ]
    xs = sorted({coordinate for x0, _, x1, _ in rectangles for coordinate in (x0, x1)})
    area = 0.0
    for left, right in zip(xs, xs[1:], strict=False):
        if right <= left:
            continue
        intervals = sorted(
            (y0, y1)
            for x0, y0, x1, y1 in rectangles
            if x0 < right and x1 > left
        )
        if not intervals:
            continue
        covered_y = 0.0
        start, end = intervals[0]
        for next_start, next_end in intervals[1:]:
            if next_start > end:
                covered_y += end - start
                start, end = next_start, next_end
            else:
                end = max(end, next_end)
        covered_y += end - start
        area += (right - left) * covered_y
    return area
