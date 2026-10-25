import json
import math
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.orm import Session

from wmrm.adapters.images.complexity import ImageComplexityInspector
from wmrm.adapters.images.inpaint import inpaint_image
from wmrm.adapters.images.masks import rasterize_image_mask
from wmrm.adapters.images.selection_risk import (
    LARGE_SELECTION_THRESHOLD,
    ImageSelectionRiskInspector,
)
from wmrm.api.schemas import (
    AnalysisResponse,
    ImageComplexityResponse,
    ImageMaskPreviewResponse,
    ImageMaskRegion,
    ImageRegionComplexity,
    ImageRegionSelectionRisk,
    ImageSelectionRiskResponse,
    PreviewImageMasksRequest,
    RenderImageMaskPreviewRequest,
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
            raise AssetError("IMAGE_MASK_NOT_AVAILABLE", "蒙版预览需要图片检查结果。", 409)
        if analysis.asset_id != asset.id or analysis.asset_sha256 != asset.sha256:
            raise AssetError("PLAN_STALE", "图片检查结果已经失效，请重新检查。", 409)

        if not request.regions and not request.polygons:
            raise AssetError("INVALID_MASK", "请至少添加一个矩形或多边形蒙版。", 422)

        for region in [*request.regions, *request.protected_regions]:
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

        for polygon in request.polygons:
            values = [coordinate for point in polygon.points for coordinate in (point.x, point.y)]
            if not all(math.isfinite(value) for value in values):
                raise AssetError("INVALID_MASK", "多边形坐标必须是有限数字。", 422)
            if polygon.transform_id != metadata.transform_id or any(
                point.x < 0
                or point.y < 0
                or point.x > metadata.display_width
                or point.y > metadata.display_height
                for point in polygon.points
            ):
                raise AssetError(
                    "PLAN_STALE",
                    "多边形坐标或图片方向已经失效，请重新检查并绘制。",
                    409,
                )
            if _polygon_area(polygon.points) < 1:
                raise AssetError("INVALID_MASK", "多边形至少需要三个不共线的顶点。", 422)

        try:
            mask = rasterize_image_mask(
                metadata.display_width,
                metadata.display_height,
                request.regions,
                request.polygons,
                request.protected_regions,
            )
        except ValueError as exc:
            raise AssetError("INVALID_MASK", str(exc), 422) from exc
        covered_pixels = float(mask.astype(bool).sum())
        if covered_pixels <= 0:
            raise AssetError(
                "EMPTY_EFFECTIVE_MASK",
                "保护区不能覆盖全部蒙版，请保留至少一个需要修复的像素区域。",
                422,
            )
        coverage_ratio = covered_pixels / (metadata.display_width * metadata.display_height)
        assessment_regions = [
            *request.regions,
            *(_polygon_bounds(item) for item in request.polygons),
        ]
        assessments = self.complexity.inspect(self.assets.path_for(asset), assessment_regions)
        risk_order = {"low": 0, "review": 1, "high": 2}
        complexity_level = max((item.risk for item in assessments), key=risk_order.__getitem__)
        complexity = ImageComplexityResponse(
            level=complexity_level,
            regions=[ImageRegionComplexity(**asdict(item)) for item in assessments],
        )
        selection_assessments = self.selection_risk.inspect(
            self.assets.path_for(asset), assessment_regions
        )
        large_selection = coverage_ratio >= LARGE_SELECTION_THRESHOLD
        low_contrast = any(item.low_contrast for item in selection_assessments)
        selection_risk = ImageSelectionRiskResponse(
            level="review" if large_selection or low_contrast else "normal",
            large_selection=large_selection,
            regions=[ImageRegionSelectionRisk(**asdict(item)) for item in selection_assessments],
        )
        requires_acknowledgement = (
            large_selection or low_contrast or metadata.animated or complexity_level == "high"
        )
        warnings = ["蒙版预览只验证计划修复的像素区域；创建处理任务后才会生成新图片。"]
        if request.protected_regions:
            warnings.append(f"已从最终修复蒙版中排除 {len(request.protected_regions)} 个保护区域。")
        if coverage_ratio > 0.25:
            warnings.append("蒙版覆盖超过图片面积的 25%，后续修复可能明显改变主体内容。")
        elif large_selection:
            warnings.append("蒙版覆盖达到图片面积的 10%；移动端基准显示大选区需要逐图对比结果。")
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
            polygons=request.polygons,
            protected_regions=request.protected_regions,
            covered_pixels=covered_pixels,
            coverage_ratio=coverage_ratio,
            complexity=complexity,
            selection_risk=selection_risk,
            requires_acknowledgement=requires_acknowledgement,
            warnings=warnings,
        )

    def render_preview(self, session: Session, request: RenderImageMaskPreviewRequest) -> bytes:
        validation = self.preview(session, request)
        if not validation.executable:
            raise AssetError(
                "IMAGE_MASK_NOT_AVAILABLE",
                "当前图片不能生成修复效果预览。",
                409,
            )
        asset = self.assets.get(session, request.asset_id)
        with TemporaryDirectory(prefix="wmrm-image-preview-") as directory:
            output_path = Path(directory) / "preview.png"
            inpaint_image(
                self.assets.path_for(asset),
                output_path,
                request.regions,
                request.radius,
                protected_regions=request.protected_regions,
                polygons=request.polygons,
            )
            return output_path.read_bytes()


def _polygon_area(points) -> float:
    return (
        abs(
            sum(
                point.x * points[(index + 1) % len(points)].y
                - points[(index + 1) % len(points)].x * point.y
                for index, point in enumerate(points)
            )
        )
        / 2
    )


def _polygon_bounds(polygon) -> ImageMaskRegion:
    return ImageMaskRegion(
        x0=min(point.x for point in polygon.points),
        y0=min(point.y for point in polygon.points),
        x1=max(point.x for point in polygon.points),
        y1=max(point.y for point in polygon.points),
        transform_id=polygon.transform_id,
    )


def rectangle_union_area(regions) -> float:
    return rectangle_difference_area(regions, [])


def rectangle_difference_area(regions, protected_regions) -> float:
    rectangles = [
        (
            math.floor(item.x0),
            math.floor(item.y0),
            math.ceil(item.x1),
            math.ceil(item.y1),
        )
        for item in regions
    ]
    protected = [
        (
            math.floor(item.x0),
            math.floor(item.y0),
            math.ceil(item.x1),
            math.ceil(item.y1),
        )
        for item in protected_regions
    ]
    xs = sorted(
        {coordinate for x0, _, x1, _ in [*rectangles, *protected] for coordinate in (x0, x1)}
    )
    area = 0.0
    for left, right in zip(xs, xs[1:], strict=False):
        if right <= left:
            continue
        intervals = sorted((y0, y1) for x0, y0, x1, y1 in rectangles if x0 < right and x1 > left)
        mask_intervals = _merge_intervals(intervals)
        if not mask_intervals:
            continue
        protected_intervals = _merge_intervals(
            sorted((y0, y1) for x0, y0, x1, y1 in protected if x0 < right and x1 > left)
        )
        covered_y = sum(end - start for start, end in mask_intervals)
        covered_y -= _interval_intersection_length(mask_intervals, protected_intervals)
        area += (right - left) * covered_y
    return area


def _merge_intervals(intervals) -> list[tuple[int, int]]:
    if not intervals:
        return []
    merged: list[tuple[int, int]] = []
    start, end = intervals[0]
    for next_start, next_end in intervals[1:]:
        if next_start > end:
            merged.append((start, end))
            start, end = next_start, next_end
        else:
            end = max(end, next_end)
    merged.append((start, end))
    return merged


def _interval_intersection_length(
    first: list[tuple[int, int]], second: list[tuple[int, int]]
) -> float:
    total = 0.0
    left_index = right_index = 0
    while left_index < len(first) and right_index < len(second):
        left = max(first[left_index][0], second[right_index][0])
        right = min(first[left_index][1], second[right_index][1])
        total += max(0, right - left)
        if first[left_index][1] <= second[right_index][1]:
            left_index += 1
        else:
            right_index += 1
    return total
