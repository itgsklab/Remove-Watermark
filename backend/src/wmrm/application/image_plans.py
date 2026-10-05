import json
import uuid

from sqlalchemy.orm import Session

from wmrm.adapters.images.selection_risk import LARGE_SELECTION_THRESHOLD
from wmrm.api.schemas import (
    ImagePlanResponse,
    PlanWarning,
    ValidateImagePlanRequest,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.application.image_masks import ImageMaskService
from wmrm.persistence.database import PlanRecord


class ImagePlanService:
    def __init__(self, assets: AssetService, masks: ImageMaskService) -> None:
        self.assets = assets
        self.masks = masks

    def validate(
        self, session: Session, request: ValidateImagePlanRequest
    ) -> ImagePlanResponse:
        asset = self.assets.get(session, request.asset_id)
        if asset.sha256 != request.asset_sha256:
            raise AssetError("PLAN_STALE", "文件摘要已变化，请重新检查。", 409)

        preview = self.masks.preview(session, request)
        if not preview.executable:
            raise AssetError(
                "IMAGE_PLAN_NOT_AVAILABLE",
                "动态图逐帧修复尚未实现，当前不能创建处理任务。",
                409,
            )

        warnings = [
            PlanWarning(
                code="IMAGE_OUTPUT_PNG",
                message="结果将保存为无损 PNG，并移除 EXIF、ICC 等原始元数据。",
                requires_acknowledgement=False,
            )
        ]
        if preview.coverage_ratio > 0.25:
            warnings.append(
                PlanWarning(
                    code="IMAGE_MASK_OVER_25_PERCENT",
                    message="蒙版覆盖超过图片面积的 25%，修复可能明显改变主体内容。",
                )
            )
        elif preview.coverage_ratio >= LARGE_SELECTION_THRESHOLD:
            warnings.append(
                PlanWarning(
                    code="IMAGE_MASK_OVER_10_PERCENT",
                    message=(
                        "蒙版覆盖达到图片面积的 10%；大选区修复必须逐图检查前后对比。"
                    ),
                )
            )
        if any(item.low_contrast for item in preview.selection_risk.regions):
            warnings.append(
                PlanWarning(
                    code="IMAGE_LOW_CONTRAST_SELECTION",
                    message=(
                        "选区与周围亮度接近，可能是半透明或低对比度水印；"
                        "基准中此类修复可能比原水印造成更大失真。"
                    ),
                )
            )
        if preview.complexity.level == "high":
            warnings.append(
                PlanWarning(
                    code="IMAGE_COMPLEXITY_HIGH",
                    message=(
                        "蒙版周围包含周期纹理、密集细节或贯穿结构线，"
                        "OpenCV 修复可能产生明显伪影。"
                    ),
                )
            )
        elif preview.complexity.level == "review":
            warnings.append(
                PlanWarning(
                    code="IMAGE_COMPLEXITY_REVIEW",
                    message="蒙版周围包含一定纹理，处理完成后请放大检查边界。",
                    requires_acknowledgement=False,
                )
            )

        acknowledged = set(request.acknowledged_warnings)
        valid = all(
            not warning.requires_acknowledgement or warning.code in acknowledged
            for warning in warnings
        )
        response = ImagePlanResponse(
            valid=valid,
            asset_id=asset.id,
            analysis_id=request.analysis_id,
            regions=request.regions,
            radius=request.radius,
            warnings=warnings,
        )
        if not valid:
            return response

        response.id = str(uuid.uuid4())
        session.add(
            PlanRecord(
                id=response.id,
                asset_id=asset.id,
                analysis_id=request.analysis_id,
                plan_json=json.dumps(
                    {
                        "kind": "image_inpaint",
                        "response": response.model_dump(mode="json"),
                        "asset_sha256": asset.sha256,
                        "regions": [item.model_dump(mode="json") for item in request.regions],
                        "radius": request.radius,
                        "complexity": preview.complexity.model_dump(mode="json"),
                        "selection_risk": preview.selection_risk.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        return response
