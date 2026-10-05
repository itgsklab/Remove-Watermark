import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from wmrm.adapters.documents.docx import DocxInspector
from wmrm.adapters.documents.docx_preview import DocxPreviewRenderer
from wmrm.adapters.images.metadata import ImageInspector
from wmrm.adapters.pdf.codecv import CodeCvPdfInspector
from wmrm.adapters.pdf.general import GeneralPdfInspector
from wmrm.adapters.pdf.preview import PdfPreviewRenderer
from wmrm.adapters.xiaohongshu.links import MetadataTransport, XiaohongshuLinkError
from wmrm.api.frontend import mount_frontend
from wmrm.api.schemas import (
    AnalysisResponse,
    AssetResponse,
    CapabilitiesResponse,
    CapabilityItem,
    CreateAnalysisRequest,
    CreateTaskRequest,
    ErrorBody,
    ErrorResponse,
    HealthResponse,
    ImageMaskPreviewResponse,
    ImagePlanResponse,
    PlanResponse,
    PreviewImageMasksRequest,
    PreviewRedactionsRequest,
    RedactionPlanResponse,
    RedactionPreviewResponse,
    TaskResponse,
    ValidateImagePlanRequest,
    ValidatePlanRequest,
    ValidateRedactionPlanRequest,
    XiaohongshuPreviewRequest,
    XiaohongshuPreviewResponse,
)
from wmrm.application.analyses import AnalysisService
from wmrm.application.assets import AssetError, AssetService, sanitize_display_name
from wmrm.application.image_masks import ImageMaskService
from wmrm.application.image_plans import ImagePlanService
from wmrm.application.plans import PlanService
from wmrm.application.redaction_plans import RedactionPlanService
from wmrm.application.redactions import RedactionService
from wmrm.application.retention import RetentionService
from wmrm.application.tasks import TaskService
from wmrm.application.xiaohongshu_links import XiaohongshuLinkService
from wmrm.persistence.database import Database
from wmrm.settings import Settings, load_settings


def create_app(
    settings: Settings | None = None,
    *,
    xiaohongshu_transport: MetadataTransport | None = None,
    frontend_dir: Path | None = None,
    shutdown_callback: Callable[[], None] | None = None,
) -> FastAPI:
    config = settings or load_settings()
    database = Database(config.database_path)
    assets = AssetService(config.data_dir, config.max_upload_bytes)
    analyses = AnalysisService(
        assets,
        DocxInspector(config.max_docx_entries, config.max_docx_uncompressed_bytes),
        CodeCvPdfInspector(config.max_pdf_pages, config.max_pdf_content_bytes),
        GeneralPdfInspector(config.max_pdf_pages, config.max_pdf_content_bytes),
        ImageInspector(
            config.max_image_dimension,
            config.max_image_pixels,
            config.max_image_frames,
        ),
    )
    plans = PlanService(assets)
    tasks = TaskService(
        assets,
        database.session_factory,
        DocxPreviewRenderer(
            enabled=config.docx_preview_enabled,
            dpi=config.docx_preview_dpi,
            max_pages=config.docx_preview_max_pages,
            timeout_seconds=config.docx_preview_timeout_seconds,
        ),
        PdfPreviewRenderer(
            enabled=config.pdf_preview_enabled,
            dpi=config.pdf_preview_dpi,
            max_pages=config.pdf_preview_max_pages,
            timeout_seconds=config.pdf_preview_timeout_seconds,
        ),
        start_method=config.worker_start_method,
        cancel_grace_seconds=config.worker_cancel_grace_seconds,
    )
    retention = RetentionService(
        assets,
        database.session_factory,
        artifact_retention_days=config.artifact_retention_days,
        unreferenced_asset_retention_days=config.unreferenced_asset_retention_days,
        failed_work_retention_hours=config.failed_work_retention_hours,
    )
    redactions = RedactionService(assets, config.pymupdf_license_mode)
    redaction_plans = RedactionPlanService(assets, redactions)
    image_masks = ImageMaskService(assets)
    image_plans = ImagePlanService(assets, image_masks)
    xiaohongshu_links = XiaohongshuLinkService(
        metadata_enabled=config.xhs_metadata_enabled,
        timeout_seconds=config.xhs_metadata_timeout_seconds,
        max_bytes=config.xhs_metadata_max_bytes,
        max_redirects=config.xhs_metadata_max_redirects,
        transport=xiaohongshu_transport,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.create_schema()
        retention.cleanup()
        tasks.start()
        tasks.recover()
        yield
        tasks.close()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        docs_url="/docs" if config.dev_cors else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = config
    app.state.database = database
    app.state.assets = assets
    app.state.analyses = analyses
    app.state.plans = plans
    app.state.tasks = tasks
    app.state.retention = retention
    app.state.redactions = redactions
    app.state.redaction_plans = redaction_plans
    app.state.image_masks = image_masks
    app.state.image_plans = image_plans
    app.state.xiaohongshu_links = xiaohongshu_links
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    if config.dev_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type", "Idempotency-Key"],
        )

    def get_session() -> Iterator[Session]:
        yield from database.session()

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            host = request.headers.get("host", "")
            allowed_origins = {f"http://{host}", f"https://{host}"}
            if config.dev_cors:
                allowed_origins.update(
                    {"http://127.0.0.1:5173", "http://localhost:5173"}
                )
            if origin and origin not in allowed_origins:
                body = ErrorResponse(
                    error=ErrorBody(
                        code="CROSS_ORIGIN_REQUEST",
                        message="已拒绝来自其他站点的本地请求。",
                        request_id=request.state.request_id,
                    )
                )
                return JSONResponse(status_code=403, content=body.model_dump(mode="json"))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if frontend_dir is not None:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' blob: data:; "
                "style-src 'self' 'unsafe-inline'; script-src 'self'; "
                "worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'"
            )
        return response

    @app.exception_handler(AssetError)
    async def asset_error_handler(request: Request, exc: AssetError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(XiaohongshuLinkError)
    async def xiaohongshu_error_handler(
        request: Request, exc: XiaohongshuLinkError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code=exc.code,
                message=exc.message,
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorBody(
                code="INVALID_REQUEST",
                message="请求参数无效。",
                details={"errors": exc.errors()},
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(version=config.app_version)

    @app.get("/api/v1/capabilities", response_model=CapabilitiesResponse)
    async def capabilities() -> CapabilitiesResponse:
        return CapabilitiesResponse(
            version=config.app_version,
            max_upload_bytes=config.max_upload_bytes,
            desktop_mode=shutdown_callback is not None,
            formats=[
                CapabilityItem(
                    id="codecv_pdf",
                    label="CodeCV 简历 PDF",
                    status="experimental",
                    strategies=["inspect", "object"],
                ),
                CapabilityItem(
                    id="docx",
                    label="Word DOCX",
                    status="experimental",
                    strategies=["inspect", "object"],
                ),
                CapabilityItem(
                    id="pdf",
                    label="PDF",
                    status="experimental",
                    strategies=["inspect", "region-redaction"],
                ),
                CapabilityItem(
                    id="image",
                    label="PNG / JPEG / WebP",
                    status="experimental",
                    strategies=["inspect", "mask-preview", "opencv-telea"],
                ),
                CapabilityItem(
                    id="xiaohongshu_link",
                    label="小红书分享链接",
                    status="experimental",
                    strategies=["share-link-parse", "metadata-preview"],
                ),
            ],
        )

    @app.post("/api/v1/system/shutdown", status_code=202)
    async def shutdown(background_tasks: BackgroundTasks) -> Response:
        if shutdown_callback is None:
            raise AssetError("SHUTDOWN_NOT_AVAILABLE", "当前启动方式不支持从页面关闭服务。", 409)
        background_tasks.add_task(shutdown_callback)
        return Response(status_code=202)

    @app.post("/api/v1/xiaohongshu/preview", response_model=XiaohongshuPreviewResponse)
    def preview_xiaohongshu_link(
        request: XiaohongshuPreviewRequest,
    ) -> XiaohongshuPreviewResponse:
        return XiaohongshuPreviewResponse.model_validate(
            xiaohongshu_links.preview(request.share_text, request.resolve_metadata)
        )

    @app.post("/api/v1/assets", response_model=AssetResponse, status_code=201)
    async def upload_asset(
        file: UploadFile,
        session: Annotated[Session, Depends(get_session)],
    ) -> AssetResponse:
        display_name = sanitize_display_name(file.filename)

        async def chunks() -> AsyncIterator[bytes]:
            while data := await file.read(config.chunk_size):
                yield data

        asset_id, inspected = await assets.stage_upload(chunks(), display_name)
        try:
            record = assets.create_record(session, asset_id, inspected, display_name)
        except Exception:
            inspected.stored_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return AssetResponse.model_validate(record)

    @app.get("/api/v1/assets/{asset_id}", response_model=AssetResponse)
    async def get_asset(
        asset_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> AssetResponse:
        return AssetResponse.model_validate(assets.get(session, asset_id))

    @app.get("/api/v1/assets/{asset_id}/content")
    async def get_asset_content(
        asset_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> FileResponse:
        asset = assets.get(session, asset_id)
        return FileResponse(
            assets.path_for(asset),
            media_type=asset.media_type,
            filename=asset.display_name,
            content_disposition_type="inline",
        )

    @app.delete("/api/v1/assets/{asset_id}", status_code=204)
    async def delete_asset(
        asset_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> Response:
        assets.delete(session, asset_id)
        return Response(status_code=204)

    @app.post("/api/v1/analyses", response_model=AnalysisResponse, status_code=201)
    async def create_analysis(
        request: CreateAnalysisRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> AnalysisResponse:
        return analyses.create(
            session,
            request.asset_id,
            request.watermark_text,
            request.preset,
        )

    @app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
    async def get_analysis(
        analysis_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> AnalysisResponse:
        return analyses.get(session, analysis_id)

    @app.post("/api/v1/plans/validate", response_model=PlanResponse)
    async def validate_plan(
        request: ValidatePlanRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> PlanResponse:
        return plans.validate(session, request)

    @app.post("/api/v1/redactions/preview", response_model=RedactionPreviewResponse)
    async def preview_redactions(
        request: PreviewRedactionsRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> RedactionPreviewResponse:
        return redactions.preview(session, request)

    @app.post(
        "/api/v1/redaction-plans/validate", response_model=RedactionPlanResponse
    )
    async def validate_redaction_plan(
        request: ValidateRedactionPlanRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> RedactionPlanResponse:
        return redaction_plans.validate(session, request)

    @app.post("/api/v1/image-masks/preview", response_model=ImageMaskPreviewResponse)
    async def preview_image_masks(
        request: PreviewImageMasksRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ImageMaskPreviewResponse:
        return image_masks.preview(session, request)

    @app.post("/api/v1/image-plans/validate", response_model=ImagePlanResponse)
    async def validate_image_plan(
        request: ValidateImagePlanRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> ImagePlanResponse:
        return image_plans.validate(session, request)

    @app.post("/api/v1/tasks", response_model=TaskResponse, status_code=202)
    async def create_task(
        request: CreateTaskRequest,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        return tasks.create(session, request.plan_id)

    @app.get("/api/v1/tasks", response_model=list[TaskResponse])
    async def list_tasks(
        session: Annotated[Session, Depends(get_session)],
    ) -> list[TaskResponse]:
        return tasks.list_tasks(session)

    @app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
    async def get_task(
        task_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        return tasks.get(session, task_id)

    @app.post("/api/v1/tasks/{task_id}/cancel", response_model=TaskResponse)
    async def cancel_task(
        task_id: str,
        session: Annotated[Session, Depends(get_session)],
    ) -> TaskResponse:
        return tasks.cancel(session, task_id)

    @app.get("/api/v1/tasks/{task_id}/artifacts/{artifact_id}")
    async def download_artifact(
        task_id: str,
        artifact_id: str,
        session: Annotated[Session, Depends(get_session)],
        inline: bool = False,
    ) -> FileResponse:
        path, display_name, media_type, is_output = tasks.artifact_path(
            session, task_id, artifact_id
        )
        if is_output and (not inline or media_type != "image/png"):
            return FileResponse(path, media_type=media_type, filename=display_name)
        return FileResponse(path, media_type=media_type)

    if frontend_dir is not None:
        mount_frontend(app, frontend_dir)

    return app


app = create_app()


def main() -> None:
    settings = load_settings()
    uvicorn.run("wmrm.api.app:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
