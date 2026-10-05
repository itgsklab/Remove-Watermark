import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from wmrm.api.schemas import (
    AnalysisResponse,
    PlanOperation,
    PlanResponse,
    PlanWarning,
    ValidatePlanRequest,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.persistence.database import AnalysisRecord, PlanRecord


class PlanService:
    def __init__(self, assets: AssetService) -> None:
        self.assets = assets

    def validate(self, session: Session, request: ValidatePlanRequest) -> PlanResponse:
        asset = self.assets.get(session, request.asset_id)
        if asset.sha256 != request.asset_sha256:
            raise AssetError("PLAN_STALE", "文件摘要已变化，请重新扫描。", 409)
        if asset.kind not in {"docx", "pdf"}:
            raise AssetError(
                "PLAN_NOT_AVAILABLE", "当前版本只支持 DOCX 和 CodeCV PDF 处理计划。", 409
            )

        analysis_record = session.scalar(
            select(AnalysisRecord).where(AnalysisRecord.id == request.analysis_id)
        )
        if analysis_record is None:
            raise AssetError("ANALYSIS_NOT_FOUND", "找不到该扫描结果。", 404)
        analysis = AnalysisResponse.model_validate(json.loads(analysis_record.result_json))
        if analysis.asset_id != asset.id or analysis.asset_sha256 != asset.sha256:
            raise AssetError("PLAN_STALE", "扫描结果与当前文件不一致，请重新扫描。", 409)
        if asset.kind == "pdf" and analysis.preset != "codecv":
            raise AssetError("PLAN_NOT_AVAILABLE", "PDF 处理仅支持 CodeCV 预设。", 409)

        candidate_by_id = {item.candidate_id: item for item in analysis.candidates}
        operation_ids = [item.candidate_id for item in request.operations]
        if len(set(operation_ids)) != len(operation_ids):
            raise AssetError("INVALID_PLAN", "处理计划包含重复候选。", 422)

        selected = []
        warnings: list[PlanWarning] = []
        for operation in request.operations:
            candidate = candidate_by_id.get(operation.candidate_id)
            if candidate is None:
                raise AssetError("INVALID_PLAN", "处理计划引用了不存在的候选。", 422)
            if operation.strategy not in candidate.allowed_strategies:
                raise AssetError("INVALID_PLAN", "候选不支持所选处理策略。", 422)
            if candidate.classification == "content":
                raise AssetError("INVALID_PLAN", "不能删除被分类为正文内容的对象。", 422)
            selected.append(candidate)
            if candidate.classification == "ambiguous":
                code = f"AMBIGUOUS_CANDIDATE:{candidate.candidate_id}"
                warnings.append(
                    PlanWarning(
                        code=code,
                        candidate_id=candidate.candidate_id,
                        message="该候选证据不足，删除前需要人工核对并明确确认。",
                    )
                )

        acknowledged = set(request.acknowledged_warnings)
        valid = all(warning.code in acknowledged for warning in warnings)
        response = PlanResponse(
            valid=valid,
            asset_id=asset.id,
            analysis_id=analysis.id,
            operations=[PlanOperation.model_validate(item) for item in request.operations],
            warnings=warnings,
            output_kind="pdf" if asset.kind == "pdf" else "docx",
        )
        if not valid:
            return response

        response.id = str(uuid.uuid4())
        session.add(
            PlanRecord(
                id=response.id,
                asset_id=asset.id,
                analysis_id=analysis.id,
                plan_json=json.dumps(
                    {
                        "response": response.model_dump(mode="json"),
                        "asset_sha256": asset.sha256,
                        "candidates": [item.model_dump(mode="json") for item in selected],
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        return response
