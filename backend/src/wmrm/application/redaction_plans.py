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
from wmrm.application.runtime_diagnostics import probe_ocr_runtime
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
                "PyMuPDF PDF 处理后端不可用，请检查运行依赖。",
                409,
            )

        overlap_count = sum(len(region.overlaps) for region in preview.regions)
        selected_ocr_languages: str | None = None
        if request.strategy == "raster_inpaint":
            ocr = probe_ocr_runtime()
            selected_ocr_languages = _validate_ocr_languages(
                request.ocr_languages,
                ocr.status,
                set(ocr.languages),
            )
            if selected_ocr_languages:
                ocr_note = (
                    "无原始文字层的页面会调用 Tesseract OCR，语言为 "
                    f"{selected_ocr_languages}。"
                )
            elif ocr.status == "unavailable":
                ocr_note = "本机未检测到 Tesseract；无原始文字层的页面可能无法搜索。"
            else:
                ocr_note = "当前计划未启用 OCR；无原始文字层的页面可能无法搜索。"
            warnings = [
                PlanWarning(
                    code="PDF_RASTERIZATION",
                    message=(
                        "所选页面将栅格化并使用 OpenCV 修复，链接、表单和矢量对象不会保留；"
                        f"原始文字层会在蒙版外回灌。{ocr_note}"
                    ),
                )
            ]
        else:
            warnings = [
                PlanWarning(
                    code="PDF_REDACTION_IRREVERSIBLE",
                    message="区域内的文字、图片像素、矢量图和链接将从输出副本中物理删除。",
                    requires_acknowledgement=False,
                )
            ]
        if preview.digital_signature_present:
            warnings.append(
                PlanWarning(
                    code="PDF_DIGITAL_SIGNATURE_INVALIDATION",
                    message=(
                        "原 PDF 包含数字签名；生成区域删除或栅格修复副本后，"
                        "现有签名验证将失效。"
                    ),
                )
            )
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
            strategy=request.strategy,
            license_mode=self.redactions.license_mode,
            regions=request.regions,
            dpi=request.dpi if request.strategy == "raster_inpaint" else None,
            radius=request.radius if request.strategy == "raster_inpaint" else None,
            ocr_languages=(
                selected_ocr_languages if request.strategy == "raster_inpaint" else None
            ),
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
                        "kind": (
                            "pdf_raster_inpaint"
                            if request.strategy == "raster_inpaint"
                            else "pdf_redaction"
                        ),
                        "response": response.model_dump(mode="json"),
                        "asset_sha256": asset.sha256,
                        "regions": [item.model_dump(mode="json") for item in request.regions],
                        "license_mode": self.redactions.license_mode,
                        "dpi": request.dpi,
                        "radius": request.radius,
                        "ocr_languages": selected_ocr_languages,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()
        return response


def _validate_ocr_languages(
    expression: str | None,
    status: str,
    installed: set[str],
) -> str | None:
    if expression is None:
        return None
    if status != "ready":
        raise AssetError(
            "OCR_LANGUAGES_UNAVAILABLE",
            "无法确认本机 OCR 语言包，请重新检查运行环境或关闭 OCR。",
            422,
        )
    requested = expression.split("+")
    missing = sorted(set(requested) - installed)
    if missing:
        raise AssetError(
            "OCR_LANGUAGES_NOT_INSTALLED",
            f"本机未安装所选 OCR 语言包：{'、'.join(missing)}。",
            422,
        )
    if len(requested) != len(set(requested)):
        raise AssetError(
            "OCR_LANGUAGES_DUPLICATED",
            "OCR 语言组合不能包含重复项。",
            422,
        )
    return "+".join(requested)
