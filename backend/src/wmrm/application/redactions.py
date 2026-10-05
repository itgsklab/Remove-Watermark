import json
import math

from sqlalchemy.orm import Session

from wmrm.adapters.pdf.pymupdf_redaction import LicenseMode, probe_pymupdf
from wmrm.api.schemas import (
    AnalysisResponse,
    PreviewRedactionsRequest,
    RedactionOverlap,
    RedactionPreviewResponse,
    RedactionRegionPreview,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.persistence.database import AnalysisRecord


class RedactionService:
    def __init__(self, assets: AssetService, license_mode: LicenseMode) -> None:
        self.assets = assets
        self.license_mode = license_mode

    def preview(
        self, session: Session, request: PreviewRedactionsRequest
    ) -> RedactionPreviewResponse:
        asset = self.assets.get(session, request.asset_id)
        if asset.kind != "pdf":
            raise AssetError("REDACTION_NOT_AVAILABLE", "区域删除预览仅支持 PDF。", 409)
        record = session.get(AnalysisRecord, request.analysis_id)
        if record is None:
            raise AssetError("ANALYSIS_NOT_FOUND", "找不到该扫描结果。", 404)
        analysis = AnalysisResponse.model_validate(json.loads(record.result_json))
        if analysis.preset != "general":
            raise AssetError(
                "REDACTION_NOT_AVAILABLE", "区域删除预览需要通用 PDF 扫描结果。", 409
            )
        if analysis.asset_id != asset.id or analysis.asset_sha256 != asset.sha256:
            raise AssetError("PLAN_STALE", "扫描结果与当前文件不一致，请重新扫描。", 409)

        pages = {item.page_number: item for item in analysis.pdf_pages}
        by_page: dict[int, list] = {}
        for item in analysis.protected_content:
            by_page.setdefault(item.region.page_number, []).append(item)

        previews = []
        overlap_count = 0
        for region in request.regions:
            page = pages.get(region.page_number)
            if page is None:
                raise AssetError("INVALID_REGION", "区域引用了不存在的 PDF 页面。", 422)
            values = (region.x0, region.y0, region.x1, region.y1)
            if not all(math.isfinite(value) for value in values):
                raise AssetError("INVALID_REGION", "区域坐标必须是有限数字。", 422)
            if (
                region.transform_id != page.transform_id
                or region.x0 < 0
                or region.y0 < 0
                or region.x1 > page.width
                or region.y1 > page.height
                or region.x0 >= region.x1
                or region.y0 >= region.y1
            ):
                raise AssetError(
                    "PLAN_STALE",
                    "区域坐标或页面变换已失效，请重新扫描并选择区域。",
                    409,
                )
            overlaps = []
            for protected in by_page.get(region.page_number, []):
                area = _intersection_area(region, protected.region)
                if area <= 0:
                    continue
                overlaps.append(
                    RedactionOverlap(
                        content_id=protected.content_id,
                        kind=protected.kind,
                        summary=protected.summary,
                        intersection_area=area,
                    )
                )
            overlap_count += len(overlaps)
            previews.append(RedactionRegionPreview(region=region, overlaps=overlaps))

        backend = probe_pymupdf()
        warnings = [
            "区域内容清单来自结构分析，超过递归限制的 Form、复杂裁剪和字体边界"
            "仍可能造成未列出的重叠。",
        ]
        if backend.available:
            warnings.append(
                "执行将使用 PyMuPDF 应用物理 redaction，并生成新的 PDF；该操作不可逆。"
            )
        else:
            warnings.append(backend.reason or "PyMuPDF 区域删除后端不可用。")
        if overlap_count:
            warnings.insert(0, f"所选区域与 {overlap_count} 个正文或交互对象相交。")
        return RedactionPreviewResponse(
            asset_id=asset.id,
            analysis_id=analysis.id,
            valid=True,
            executable=backend.available,
            requires_acknowledgement=overlap_count > 0,
            regions=previews,
            warnings=warnings,
        )


def _intersection_area(first, second) -> float:
    width = min(first.x1, second.x1) - max(first.x0, second.x0)
    height = min(first.y1, second.y1) - max(first.y0, second.y0)
    return max(0.0, width) * max(0.0, height)
