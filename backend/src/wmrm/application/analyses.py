import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from wmrm.adapters.documents.docx import DocxInspector
from wmrm.adapters.images.metadata import ImageInspector
from wmrm.adapters.pdf.codecv import CodeCvPdfInspector
from wmrm.adapters.pdf.general import GeneralPdfInspector
from wmrm.api.schemas import (
    AnalysisResponse,
    CandidateResponse,
    ImageMetadataResponse,
    SourceLocator,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.persistence.database import AnalysisRecord


class AnalysisService:
    def __init__(
        self,
        assets: AssetService,
        docx_inspector: DocxInspector,
        codecv_inspector: CodeCvPdfInspector,
        general_pdf_inspector: GeneralPdfInspector,
        image_inspector: ImageInspector,
    ) -> None:
        self.assets = assets
        self.docx_inspector = docx_inspector
        self.codecv_inspector = codecv_inspector
        self.general_pdf_inspector = general_pdf_inspector
        self.image_inspector = image_inspector

    def create(
        self,
        session: Session,
        asset_id: str,
        watermark_text: str | None,
        preset: str | None = None,
    ) -> AnalysisResponse:
        asset = self.assets.get(session, asset_id)
        image_metadata = None
        if asset.kind == "docx" and preset is None:
            inspection = self.docx_inspector.inspect(
                self.assets.path_for(asset),
                asset.sha256,
                watermark_text,
            )
            candidates = [
                CandidateResponse(
                    candidate_id=item.candidate_id,
                    classification=item.classification,
                    kind=item.kind,
                    content=item.content,
                    evidence=item.evidence,
                    source_locator=SourceLocator(
                        part_name=item.part_name,
                        shape_index=item.shape_index,
                        shape_id=item.shape_id,
                        shape_type=item.shape_type,
                    ),
                    style=item.style,
                    allowed_strategies=list(item.allowed_strategies),
                )
                for item in inspection.candidates
            ]
            inspected_parts = list(inspection.inspected_parts)
            warnings = list(inspection.warnings)
            match_status = None
            pdf_pages = []
            protected_content = []
        elif asset.kind == "pdf" and preset == "codecv":
            inspection = self.codecv_inspector.inspect(
                self.assets.path_for(asset), asset.sha256
            )
            candidates = [
                CandidateResponse(
                    candidate_id=item.candidate_id,
                    classification=item.classification,
                    kind=item.kind,
                    content=item.content,
                    evidence=item.evidence,
                    source_locator=SourceLocator(
                        page_numbers=[item.page_number],
                        resource_name=item.resource_name,
                        object_number=item.object_number,
                        generation_number=item.generation_number,
                        operation_index=item.operation_index,
                    ),
                    style=item.style,
                    allowed_strategies=list(item.allowed_strategies),
                )
                for item in inspection.candidates
            ]
            inspected_parts = list(inspection.inspected_parts)
            warnings = list(inspection.warnings)
            match_status = inspection.match_status
            pdf_pages = []
            protected_content = []
        elif asset.kind == "pdf" and preset == "general":
            inspection = self.general_pdf_inspector.inspect(
                self.assets.path_for(asset), asset.sha256, watermark_text
            )
            candidates = [
                CandidateResponse(
                    candidate_id=item.candidate_id,
                    classification=item.classification,
                    kind=item.kind,
                    content=item.content,
                    evidence=item.evidence,
                    source_locator=SourceLocator(
                        page_numbers=[item.page_number] if item.page_number else [],
                        resource_name=item.resource_name,
                        object_number=item.object_number,
                        generation_number=item.generation_number,
                        operation_index=item.operation_index,
                        annotation_index=item.annotation_index,
                    ),
                    style=item.style,
                    allowed_strategies=list(item.allowed_strategies),
                    region=item.region,
                    overlaps_protected_content=item.overlaps_protected_content,
                )
                for item in inspection.candidates
            ]
            inspected_parts = list(inspection.inspected_parts)
            warnings = list(inspection.warnings)
            match_status = inspection.match_status
            pdf_pages = list(inspection.pdf_pages)
            protected_content = list(inspection.protected_content)
        elif asset.kind in {"png", "jpeg", "webp"} and preset == "image":
            inspection = self.image_inspector.inspect(
                self.assets.path_for(asset), asset.sha256, asset.kind
            )
            candidates = []
            inspected_parts = list(inspection.inspected_parts)
            warnings = list(inspection.warnings)
            match_status = "not_found"
            pdf_pages = []
            protected_content = []
            image_metadata = ImageMetadataResponse(
                width=inspection.width,
                height=inspection.height,
                display_width=inspection.display_width,
                display_height=inspection.display_height,
                format=inspection.format,
                mode=inspection.mode,
                frames=inspection.frames,
                animated=inspection.animated,
                has_alpha=inspection.has_alpha,
                exif_orientation=inspection.exif_orientation,
                has_icc_profile=inspection.has_icc_profile,
                transform_id=inspection.transform_id,
            )
        else:
            message = (
                "图片检查需要显式选择图片预设。"
                if asset.kind in {"png", "jpeg", "webp"}
                else "PDF 扫描需要显式选择 CodeCV 或通用 PDF 预设。"
            )
            raise AssetError(
                "ANALYSIS_NOT_AVAILABLE",
                message,
                409,
            )
        analysis_id = str(uuid.uuid4())
        response = AnalysisResponse(
            id=analysis_id,
            asset_id=asset_id,
            asset_sha256=asset.sha256,
            status="complete",
            candidates=candidates,
            inspected_parts=inspected_parts,
            warnings=warnings,
            preset=preset,
            match_status=match_status,
            pdf_pages=pdf_pages,
            protected_content=protected_content,
            image_metadata=image_metadata,
        )
        session.add(
            AnalysisRecord(
                id=analysis_id,
                asset_id=asset_id,
                status=response.status,
                result_json=response.model_dump_json(),
            )
        )
        session.commit()
        return response

    def get(self, session: Session, analysis_id: str) -> AnalysisResponse:
        record = session.scalar(
            select(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
        )
        if record is None:
            raise AssetError("ANALYSIS_NOT_FOUND", "找不到该扫描结果。", 404)
        return AnalysisResponse.model_validate(json.loads(record.result_json))
