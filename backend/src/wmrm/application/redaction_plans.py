import json
import uuid

from sqlalchemy.orm import Session

from wmrm.api.schemas import (
    PlanWarning,
    RedactionPlanResponse,
    ValidateRedactionPlanRequest,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.application.redactions import RedactionService
from wmrm.persistence.database import PlanRecord


class RedactionPlanService:
    def __init__(self, assets: AssetService, redactions: RedactionService) -> None:
        self.assets = assets
        self.redactions = redactions

    def validate(
        self, session: Session, request: ValidateRedactionPlanRequest
    ) -> RedactionPlanResponse:
        asset = self.assets.get(session, request.asset_id)
        if asset.sha256 != request.asset_sha256:
            raise AssetError("PLAN_STALE", "文件摘要已变化，请重新扫描。", 409)

        preview = self.redactions.preview(session, request)
        if not preview.executable:
            raise AssetError(
                "REDACTION_BACKEND_UNAVAILABLE",
                "PyMuPDF 区域删除后端不可用，请检查运行依赖。",
                409,
            )

        overlap_count = sum(len(region.overlaps) for region in preview.regions)
        warnings = [
            PlanWarning(
                code="PDF_REDACTION_IRREVERSIBLE",
                message="区域内的文字、图片像素、矢量图和链接将从输出副本中物理删除。",
                requires_acknowledgement=False,
            )
        ]
        if overlap_count:
            warnings.append(
                PlanWarning(
                    code="PDF_REDACTION_OVERLAP",
                    message=f"所选区域与 {overlap_count} 个正文或交互对象相交。",
                )
            )

        acknowledged = set(request.acknowledged_warnings)
        valid = all(
            not warning.requires_acknowledgement or warning.code in acknowledged
            for warning in warnings
        )
        response = RedactionPlanResponse(
            valid=valid,
            asset_id=asset.id,
            analysis_id=request.analysis_id,
            license_mode=self.redactions.license_mode,
            regions=request.regions,
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
                        "kind": "pdf_redaction",
                        "response": response.model_dump(mode="json"),
                        "asset_sha256": asset.sha256,
                        "regions": [item.model_dump(mode="json") for item in request.regions],
                        "license_mode": self.redactions.license_mode,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        return response
