import json
import uuid

from sqlalchemy.orm import Session

from wmrm.adapters.images.plan_risk import build_image_plan_warnings
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
                code=warning.code,
                message=warning.message,
                requires_acknowledgement=warning.requires_acknowledgement,
            )
            for warning in build_image_plan_warnings(
                preview.coverage_ratio,
                preview.selection_risk.regions,
                preview.complexity.level,
            )
        ]

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
