from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class CapabilityItem(BaseModel):
    id: str
    label: str
    status: Literal["available", "planned", "experimental"]
    strategies: list[str]


class OptionalModelCapability(BaseModel):
    enabled: bool
    available: bool
    status: Literal["disabled", "configuration_invalid", "runtime_missing", "ready"]
    model_id: str | None = None
    automatic_download: Literal[False] = False
    requires_manual_review: Literal[True] = True
    message: str


class OcrRuntimeDiagnostic(BaseModel):
    available: bool
    status: Literal["unavailable", "ready", "probe_failed"]
    version: str | None = None
    languages: list[str] = Field(default_factory=list)
    message: str


class XiaohongshuRuntimeDiagnostic(BaseModel):
    status: Literal["parse_only", "metadata_only", "ready", "configuration_invalid"]
    share_link_parsing: Literal[True] = True
    metadata_reading_enabled: bool
    image_import_enabled: bool
    proxy_configured: bool
    message: str


class RuntimeDiagnosticsResponse(BaseModel):
    schema_version: Literal[1] = 1
    ocr: OcrRuntimeDiagnostic
    xiaohongshu: XiaohongshuRuntimeDiagnostic
    vlm_localization: OptionalModelCapability


class CapabilitiesResponse(BaseModel):
    version: str
    max_upload_bytes: int
    formats: list[CapabilityItem]
    vlm_localization: OptionalModelCapability


class XiaohongshuPreviewRequest(BaseModel):
    share_text: str = Field(min_length=1, max_length=4096)
    resolve_metadata: bool = False


class XiaohongshuMediaCandidateResponse(BaseModel):
    candidate_id: str
    position: int = Field(ge=1)
    role: Literal["cover", "gallery"]


class XiaohongshuPreviewResponse(BaseModel):
    kind: Literal["direct", "short"]
    normalized_url: str
    canonical_url: str | None
    note_id: str | None
    metadata_status: Literal["not_requested", "disabled", "resolved", "unavailable"]
    title: str | None
    description: str | None
    author: str | None
    thumbnail_present: bool
    media_download_supported: bool
    media_candidates: list[XiaohongshuMediaCandidateResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class XiaohongshuImportRequest(BaseModel):
    share_text: str = Field(min_length=1, max_length=4096)
    candidate_id: str = Field(pattern=r"^xhs-image-[a-f0-9]{20}$")


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    kind: str
    media_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class CreateAnalysisRequest(BaseModel):
    asset_id: str
    watermark_text: str | None = Field(default=None, max_length=200)
    preset: Literal["codecv", "general", "image"] | None = None


class CandidateRegion(BaseModel):
    coordinate_space: Literal["pdf_points"] = "pdf_points"
    page_number: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float = Field(gt=0)
    page_height: float = Field(gt=0)
    rotation: int
    transform_id: str = ""
    approximate: bool = False


class PdfPageGeometry(BaseModel):
    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: int
    crop_x: float = 0
    crop_y: float = 0
    transform_id: str


class ImageMetadataResponse(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    display_width: int = Field(gt=0)
    display_height: int = Field(gt=0)
    format: Literal["PNG", "JPEG", "WEBP"]
    mode: str
    frames: int = Field(ge=1)
    animated: bool
    has_alpha: bool
    exif_orientation: int = Field(ge=1, le=8)
    has_icc_profile: bool
    transform_id: str


class ProtectedContentResponse(BaseModel):
    content_id: str
    kind: Literal["text", "image", "form", "graphic", "link", "annotation"]
    summary: str
    region: CandidateRegion


class SourceLocator(BaseModel):
    part_name: str | None = None
    shape_index: int | None = Field(default=None, ge=0)
    shape_id: str | None = None
    shape_type: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    resource_name: str | None = None
    object_number: int | None = Field(default=None, ge=0)
    generation_number: int | None = Field(default=None, ge=0)
    operation_index: int | None = Field(default=None, ge=0)
    annotation_index: int | None = Field(default=None, ge=0)
    drawing_index: int | None = Field(default=None, ge=0)
    relationship_id: str | None = None
    media_part_name: str | None = None
    media_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class CandidateResponse(BaseModel):
    candidate_id: str
    classification: Literal["confirmed", "ambiguous", "content"]
    kind: Literal["text", "image", "pattern", "other"]
    content: str | None
    evidence: str
    source_locator: SourceLocator
    style: str | None
    allowed_strategies: list[str]
    region: CandidateRegion | None = None
    overlaps_protected_content: bool | None = None
    preview_url: str | None = None
    preview_media_type: Literal["image/png", "image/jpeg", "image/gif", "image/webp"] | None = None


class AnalysisResponse(BaseModel):
    id: str
    asset_id: str
    asset_sha256: str
    status: Literal["complete"]
    candidates: list[CandidateResponse]
    inspected_parts: list[str]
    warnings: list[str]
    preset: Literal["codecv", "general", "image"] | None = None
    match_status: Literal["matched", "needs_review", "not_found"] | None = None
    pdf_pages: list[PdfPageGeometry] = Field(default_factory=list)
    protected_content: list[ProtectedContentResponse] = Field(default_factory=list)
    image_metadata: ImageMetadataResponse | None = None


class RedactionRegionRequest(BaseModel):
    page_number: int = Field(ge=1)
    x0: float
    y0: float
    x1: float
    y1: float
    transform_id: str = Field(min_length=1, max_length=64)


class PreviewRedactionsRequest(BaseModel):
    asset_id: str
    analysis_id: str
    regions: list[RedactionRegionRequest] = Field(min_length=1, max_length=100)
    strategy: Literal["pymupdf_redaction", "raster_inpaint"] = "pymupdf_redaction"


class RedactionOverlap(BaseModel):
    content_id: str
    kind: str
    summary: str
    intersection_area: float = Field(gt=0)


class RedactionRegionPreview(BaseModel):
    region: RedactionRegionRequest
    overlaps: list[RedactionOverlap]


class RedactionPreviewResponse(BaseModel):
    asset_id: str
    analysis_id: str
    valid: bool
    requires_acknowledgement: bool
    executable: bool
    regions: list[RedactionRegionPreview]
    warnings: list[str]


class ValidateRedactionPlanRequest(PreviewRedactionsRequest):
    asset_sha256: str = Field(min_length=64, max_length=64)
    dpi: int = Field(default=144, ge=96, le=300)
    radius: int = Field(default=3, ge=1, le=10)
    ocr_languages: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*$",
    )
    acknowledged_warnings: list[str] = Field(default_factory=list)


class ImageMaskRegion(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    transform_id: str = Field(min_length=1, max_length=64)


class VlmSuggestionRequest(BaseModel):
    asset_id: str
    analysis_id: str


class PhotoSceneAssessmentResponse(BaseModel):
    eligible: bool
    matched_routes: list[str]
    reasons: list[str]


class VlmSuggestionResponse(BaseModel):
    asset_id: str
    analysis_id: str
    status: Literal["suggested", "no_candidates", "photo_gate_rejected"]
    regions: list[ImageMaskRegion]
    photo_scene: PhotoSceneAssessmentResponse
    warnings: list[str]


class PreviewImageMasksRequest(BaseModel):
    asset_id: str
    analysis_id: str
    regions: list[ImageMaskRegion] = Field(min_length=1, max_length=100)
    protected_regions: list[ImageMaskRegion] = Field(default_factory=list, max_length=100)


class ImageRegionComplexity(BaseModel):
    region_index: int = Field(ge=0)
    risk: Literal["low", "review", "high"]
    texture_score: float = Field(ge=0, le=1)
    edge_density: float = Field(ge=0, le=1)
    periodicity_score: float = Field(ge=0, le=1)
    structure_score: float = Field(ge=0, le=1)
    context_pixels: int = Field(ge=0)
    reasons: list[str]


class ImageComplexityResponse(BaseModel):
    level: Literal["low", "review", "high"]
    regions: list[ImageRegionComplexity]


class ImageRegionSelectionRisk(BaseModel):
    region_index: int = Field(ge=0)
    mean_luma_delta: float = Field(ge=0, le=1)
    low_contrast: bool
    reason: str


class ImageSelectionRiskResponse(BaseModel):
    level: Literal["normal", "review"]
    large_selection: bool
    regions: list[ImageRegionSelectionRisk]


class ImageMaskPreviewResponse(BaseModel):
    asset_id: str
    analysis_id: str
    valid: bool
    executable: bool
    regions: list[ImageMaskRegion]
    protected_regions: list[ImageMaskRegion] = Field(default_factory=list)
    covered_pixels: float = Field(gt=0)
    coverage_ratio: float = Field(gt=0, le=1)
    complexity: ImageComplexityResponse
    selection_risk: ImageSelectionRiskResponse
    requires_acknowledgement: bool
    warnings: list[str]


class PlanOperation(BaseModel):
    candidate_id: str
    strategy: Literal["object"] = "object"


class ValidatePlanRequest(BaseModel):
    asset_id: str
    asset_sha256: str
    analysis_id: str
    operations: list[PlanOperation] = Field(min_length=1)
    acknowledged_warnings: list[str] = Field(default_factory=list)


class PlanWarning(BaseModel):
    code: str
    candidate_id: str | None = None
    message: str
    requires_acknowledgement: bool = True


class RedactionPlanResponse(BaseModel):
    id: str | None = None
    valid: bool
    asset_id: str
    analysis_id: str
    strategy: Literal["pymupdf_redaction", "raster_inpaint"] = "pymupdf_redaction"
    license_mode: Literal["agpl", "commercial"]
    regions: list[RedactionRegionRequest]
    dpi: int | None = None
    radius: int | None = None
    ocr_languages: str | None = None
    warnings: list[PlanWarning]
    output_kind: Literal["pdf"] = "pdf"


class ValidateImagePlanRequest(BaseModel):
    asset_id: str
    asset_sha256: str
    analysis_id: str
    regions: list[ImageMaskRegion] = Field(min_length=1, max_length=100)
    protected_regions: list[ImageMaskRegion] = Field(default_factory=list, max_length=100)
    radius: int = Field(default=3, ge=1, le=10)
    acknowledged_warnings: list[str] = Field(default_factory=list)


class ImagePlanResponse(BaseModel):
    id: str | None = None
    valid: bool
    asset_id: str
    analysis_id: str
    strategy: Literal["opencv_telea"] = "opencv_telea"
    regions: list[ImageMaskRegion]
    protected_regions: list[ImageMaskRegion] = Field(default_factory=list)
    radius: int
    warnings: list[PlanWarning]
    output_kind: Literal["png"] = "png"


class PlanResponse(BaseModel):
    id: str | None = None
    valid: bool
    asset_id: str
    analysis_id: str
    operations: list[PlanOperation]
    warnings: list[PlanWarning]
    output_kind: Literal["docx", "pdf"] = "docx"


class CreateTaskRequest(BaseModel):
    plan_id: str


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    media_type: str
    size_bytes: int
    sha256: str
    download_url: str
    role: Literal["output", "source_preview", "result_preview"]
    page_number: int | None = None


class ComparisonPage(BaseModel):
    page_number: int
    source_url: str | None = None
    result_url: str | None = None


class ComparisonResponse(BaseModel):
    available: bool
    removed_count: int
    changed_parts: list[str]
    source_page_count: int
    result_page_count: int
    pages: list[ComparisonPage]
    warning: str | None = None


class TaskResponse(BaseModel):
    id: str
    plan_id: str
    status: Literal["queued", "running", "cancelling", "cancelled", "succeeded", "failed"]
    stage: str
    progress: float = Field(ge=0, le=1)
    created_at: datetime
    updated_at: datetime
    duration_seconds: float = Field(ge=0)
    warning_codes: list[str] = Field(default_factory=list)
    error: ErrorBody | None = None
    artifacts: list[ArtifactResponse] = Field(default_factory=list)
    comparison: ComparisonResponse | None = None
    report_url: str


class TaskReportInput(BaseModel):
    asset_id: str
    kind: str
    media_type: str
    size_bytes: int
    sha256: str


class TaskReportPdfPage(BaseModel):
    page_number: int = Field(ge=1)
    text_source: Literal["source_text", "ocr", "none"]
    ocr_status: Literal[
        "not_needed", "succeeded", "disabled", "unavailable", "failed", "no_text"
    ]
    word_count: int = Field(ge=0)
    searchable: bool
    unsearchable_reason: Literal[
        "ocr_disabled",
        "ocr_unavailable",
        "ocr_failed",
        "ocr_no_text",
        "text_layer_insert_failed",
    ] | None = None


class TaskReportProcessing(BaseModel):
    kind: str
    output_kind: str
    selected_target_count: int = Field(ge=0)
    protected_target_count: int = Field(default=0, ge=0)
    warning_codes: list[str] = Field(default_factory=list)
    radius: int | None = None
    dpi: int | None = None
    ocr_languages: str | None = None
    pdf_pages: list[TaskReportPdfPage] = Field(default_factory=list)


class TaskReportArtifact(BaseModel):
    id: str
    role: Literal["output", "source_preview", "result_preview"]
    media_type: str
    size_bytes: int
    sha256: str
    page_number: int | None = None


class TaskReportComparison(BaseModel):
    available: bool
    removed_count: int
    source_page_count: int
    result_page_count: int


class TaskReportError(BaseModel):
    code: str


class TaskReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    task_id: str
    plan_id: str
    status: Literal["queued", "running", "cancelling", "cancelled", "succeeded", "failed"]
    stage: str
    progress: float = Field(ge=0, le=1)
    created_at: datetime
    updated_at: datetime
    duration_seconds: float = Field(ge=0)
    input: TaskReportInput
    processing: TaskReportProcessing
    artifacts: list[TaskReportArtifact] = Field(default_factory=list)
    comparison: TaskReportComparison | None = None
    error: TaskReportError | None = None
