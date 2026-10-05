import json
import queue
import shutil
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from threading import Event, Lock, Thread
from time import monotonic
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from wmrm.adapters.documents.docx_preview import DocxPreviewRenderer
from wmrm.adapters.pdf.preview import PdfPreviewRenderer
from wmrm.api.schemas import (
    ArtifactResponse,
    ComparisonPage,
    ComparisonResponse,
    ErrorBody,
    TaskResponse,
)
from wmrm.application.assets import AssetError, AssetService
from wmrm.application.worker import run_task_process
from wmrm.persistence.database import ArtifactRecord, PlanRecord, TaskRecord

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MEDIA_TYPE = "application/pdf"
PNG_MEDIA_TYPE = "image/png"
IMAGE_KINDS = {"png", "jpeg", "webp"}
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@dataclass(slots=True)
class _ActiveProcess:
    process: Any
    cancel_event: Any


WorkerEntrypoint = Callable[[dict[str, Any], Any, Any], None]


class TaskService:
    def __init__(
        self,
        assets: AssetService,
        session_factory: sessionmaker[Session],
        docx_preview_renderer: DocxPreviewRenderer,
        pdf_preview_renderer: PdfPreviewRenderer,
        worker_entrypoint: WorkerEntrypoint | None = None,
        start_method: str = "spawn",
        cancel_grace_seconds: float = 2.0,
    ) -> None:
        self.assets = assets
        self.session_factory = session_factory
        self.docx_preview_renderer = docx_preview_renderer
        self.pdf_preview_renderer = pdf_preview_renderer
        self.worker_entrypoint = worker_entrypoint or run_task_process
        self.cancel_grace_seconds = cancel_grace_seconds
        self.process_context = get_context(start_method)
        self.pending: queue.Queue[str] = queue.Queue()
        self.stop_event = Event()
        self.supervisor = Thread(
            target=self._supervise,
            name="wmrm-process-supervisor",
            daemon=True,
        )
        self.started = False
        self.active: dict[str, _ActiveProcess] = {}
        self.active_lock = Lock()
        self.artifact_root = assets.data_dir / "artifacts"
        self.artifact_root.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        if self.started:
            return
        self.started = True
        self.supervisor.start()

    def close(self) -> None:
        self.stop_event.set()
        with self.active_lock:
            active = list(self.active.values())
        for item in active:
            item.cancel_event.set()
        if self.started:
            self.supervisor.join(timeout=self.cancel_grace_seconds + 2)
        with self.active_lock:
            active = list(self.active.values())
        for item in active:
            if item.process.is_alive():
                self._stop_process(item.process)

    def create(self, session: Session, plan_id: str) -> TaskResponse:
        plan = session.scalar(select(PlanRecord).where(PlanRecord.id == plan_id))
        if plan is None:
            raise AssetError("PLAN_NOT_FOUND", "找不到该处理计划。", 404)
        payload = json.loads(plan.plan_json)
        if not payload["response"]["valid"]:
            raise AssetError("INVALID_PLAN", "处理计划未通过校验。", 422)
        asset = self.assets.get(session, plan.asset_id)
        if asset.sha256 != payload["asset_sha256"]:
            raise AssetError("PLAN_STALE", "文件摘要已变化，请重新扫描。", 409)

        task_id = str(uuid.uuid4())
        session.add(
            TaskRecord(
                id=task_id,
                plan_id=plan.id,
                status="queued",
                stage="等待执行",
                progress=0.0,
            )
        )
        session.commit()
        self._enqueue(task_id)
        session.expire_all()
        return self.get(session, task_id)

    def _enqueue(self, task_id: str) -> None:
        self.pending.put(task_id)

    def _supervise(self) -> None:
        while not self.stop_event.is_set():
            try:
                task_id = self.pending.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._execute(task_id)
            finally:
                self.pending.task_done()

    def _execute(self, task_id: str) -> None:
        try:
            with self.session_factory() as session:
                record = session.get(TaskRecord, task_id)
                if record is None or record.status != "queued":
                    return
                plan = session.get(PlanRecord, record.plan_id)
                if plan is None:
                    raise AssetError("PLAN_NOT_FOUND", "找不到该处理计划。", 404)
                payload = json.loads(plan.plan_json)
                plan_kind = str(payload.get("kind", "object_removal"))
                asset = self.assets.get(session, plan.asset_id)
                if asset.sha256 != payload["asset_sha256"]:
                    raise AssetError("PLAN_STALE", "文件摘要已变化，请重新扫描。", 409)
                source_path = self.assets.path_for(asset)
                record.status = "running"
                is_pdf = asset.kind == "pdf"
                is_image = asset.kind in IMAGE_KINDS
                record.stage = (
                    "使用 OpenCV 修复并校验图片"
                    if is_image
                    else "应用并校验 PDF 区域删除"
                    if plan_kind == "pdf_redaction"
                    else "生成并校验 PDF"
                    if is_pdf
                    else "生成并校验 DOCX"
                )
                record.progress = 0.2
                record.error_json = None
                session.commit()
                extension = "png" if is_image else "pdf" if is_pdf else "docx"
                output_path = self.artifact_root / task_id / f"result.{extension}"
                source_name = asset.display_name
                asset_kind = asset.kind
                request = {
                    "asset_kind": asset_kind,
                    "plan_kind": plan_kind,
                    "source_path": str(source_path),
                    "output_path": str(output_path),
                    "preview_path": str(self.artifact_root / task_id / "preview"),
                    "candidates": payload.get("candidates", []),
                    "regions": payload.get("regions", []),
                    "radius": payload.get("radius", 3),
                    "license_mode": payload.get("license_mode"),
                    "preview_config": self._preview_config(is_pdf),
                }
            result_queue = self.process_context.Queue(maxsize=1)
            cancel_event = self.process_context.Event()
            process = self.process_context.Process(
                target=self.worker_entrypoint,
                args=(request, result_queue, cancel_event),
                name=f"wmrm-task-{task_id[:8]}",
            )
            with self.active_lock:
                self.active[task_id] = _ActiveProcess(process, cancel_event)
            with self.session_factory() as session:
                current = session.get(TaskRecord, task_id)
                if current is None or current.status != "running":
                    cancel_event.set()
            process.start()
            outcome = self._wait_for_process(process, result_queue, cancel_event)
            if self.stop_event.is_set():
                return
            self._finish(task_id, source_name, asset_kind, plan_kind, outcome)
        except Exception as exc:
            if not self.stop_event.is_set():
                self._mark_start_failed(task_id, exc)
        finally:
            with self.active_lock:
                self.active.pop(task_id, None)

    def _mark_start_failed(self, task_id: str, exc: Exception) -> None:
        with self.session_factory() as session:
            record = session.get(TaskRecord, task_id)
            if record is None or record.status in TERMINAL_STATUSES:
                return
            record.status = "failed"
            record.stage = "任务无法启动"
            record.progress = 1.0
            record.error_json = json.dumps(
                {"code": "TASK_START_FAILED", "message": str(exc)}, ensure_ascii=False
            )
            session.commit()

    def _wait_for_process(self, process, result_queue, cancel_event) -> dict[str, Any]:
        cancel_deadline = None
        while process.is_alive():
            process.join(timeout=0.05)
            if self.stop_event.is_set() or cancel_event.is_set():
                cancel_event.set()
                cancel_deadline = cancel_deadline or monotonic() + self.cancel_grace_seconds
                if monotonic() >= cancel_deadline and process.is_alive():
                    self._stop_process(process)
        process.join()
        try:
            return result_queue.get(timeout=0.5)
        except queue.Empty:
            if cancel_event.is_set():
                return {"status": "cancelled"}
            return {
                "status": "failed",
                "error": f"Worker 进程异常退出（exit code {process.exitcode}）。",
            }
        finally:
            result_queue.close()
            result_queue.join_thread()

    @staticmethod
    def _stop_process(process) -> None:
        process.terminate()
        process.join(timeout=1)
        if process.is_alive():
            process.kill()
            process.join(timeout=1)

    def _finish(
        self,
        task_id: str,
        source_name: str,
        asset_kind: str,
        plan_kind: str,
        outcome: dict[str, Any],
    ) -> None:
        with self.session_factory() as session:
            record = session.get(TaskRecord, task_id)
            if record is None:
                return
            try:
                if record.status == "cancelling" or outcome["status"] == "cancelled":
                    record.status = "cancelled"
                    record.stage = "任务已取消"
                    record.progress = 1.0
                    record.error_json = None
                    self._remove_task_files(task_id)
                elif outcome["status"] == "succeeded":
                    result = outcome["result"]
                    preview = outcome["preview"]
                    is_pdf = asset_kind == "pdf"
                    is_image = asset_kind in IMAGE_KINDS
                    extension = "png" if is_image else "pdf" if is_pdf else "docx"
                    output_path = self.artifact_root / task_id / f"result.{extension}"
                    display_stem = Path(source_name).stem[:220] or "document"
                    artifacts = [
                        ArtifactRecord(
                            id=str(uuid.uuid4()),
                            task_id=task_id,
                            relative_path=output_path.relative_to(
                                self.assets.data_dir
                            ).as_posix(),
                            display_name=f"{display_stem}-cleaned.{extension}",
                            media_type=(
                                PNG_MEDIA_TYPE
                                if is_image
                                else PDF_MEDIA_TYPE
                                if is_pdf
                                else DOCX_MEDIA_TYPE
                            ),
                            size_bytes=int(result["size_bytes"]),
                            sha256=str(result["sha256"]),
                        )
                    ]
                    artifacts.extend(
                        ArtifactRecord(
                            id=str(uuid.uuid4()),
                            task_id=task_id,
                            relative_path=Path(image["path"])
                            .relative_to(self.assets.data_dir)
                            .as_posix(),
                            display_name=(
                                f"{image['side']}-page-{image['page_number']}.png"
                            ),
                            media_type="image/png",
                            size_bytes=int(image["size_bytes"]),
                            sha256=str(image["sha256"]),
                        )
                        for image in preview["images"]
                    )
                    session.add_all(artifacts)
                    record.status = "succeeded"
                    record.stage = (
                        f"已修复 {result['removed_count']} 个蒙版区域并完成像素校验"
                        if is_image
                        else f"已物理删除 {result['removed_count']} 个 PDF 区域并完成校验"
                        if plan_kind == "pdf_redaction"
                        else f"已删除 {result['removed_count']} 个候选并完成校验"
                    )
                    if not is_image and not preview["available"]:
                        record.stage += "；页面预览不可用"
                    record.progress = 1.0
                else:
                    raise RuntimeError(str(outcome.get("error", "Worker 处理失败。")))
            except Exception as exc:
                session.rollback()
                record = session.get(TaskRecord, task_id)
                if record is not None:
                    record.status = "failed"
                    record.stage = "处理失败"
                    record.progress = 1.0
                    record.error_json = json.dumps(
                        {"code": "PROCESSING_FAILED", "message": str(exc)},
                        ensure_ascii=False,
                    )
                self._remove_task_files(task_id)
            session.commit()

    def _preview_config(self, is_pdf: bool) -> dict[str, Any]:
        renderer = self.pdf_preview_renderer if is_pdf else self.docx_preview_renderer
        return {
            "enabled": renderer.enabled,
            "dpi": renderer.dpi,
            "max_pages": renderer.max_pages,
            "timeout_seconds": renderer.timeout_seconds,
        }

    def cancel(self, session: Session, task_id: str) -> TaskResponse:
        record = session.get(TaskRecord, task_id)
        if record is None:
            raise AssetError("TASK_NOT_FOUND", "找不到该处理任务。", 404)
        if record.status == "cancelled":
            return self.get(session, task_id)
        if record.status in TERMINAL_STATUSES:
            raise AssetError("TASK_NOT_CANCELLABLE", "该任务已经结束，无法取消。", 409)
        record.status = "cancelling"
        record.stage = "正在取消"
        session.commit()
        with self.active_lock:
            active = self.active.get(task_id)
        if active is None:
            record.status = "cancelled"
            record.stage = "任务已取消"
            record.progress = 1.0
            session.commit()
            self._remove_task_files(task_id)
        else:
            active.cancel_event.set()
        session.expire_all()
        return self.get(session, task_id)

    def recover(self) -> None:
        resumable: list[str] = []
        with self.session_factory() as session:
            records = session.scalars(
                select(TaskRecord).where(
                    TaskRecord.status.in_(["queued", "running", "cancelling"])
                )
            ).all()
            for record in records:
                self._remove_task_files(record.id)
                session.execute(
                    delete(ArtifactRecord).where(ArtifactRecord.task_id == record.id)
                )
                if record.status == "cancelling":
                    record.status = "cancelled"
                    record.stage = "服务重启后完成取消"
                    record.progress = 1.0
                else:
                    record.status = "queued"
                    record.stage = "服务重启后重新排队"
                    record.progress = 0.0
                    record.error_json = None
                    resumable.append(record.id)
            session.commit()
        for task_id in resumable:
            self._enqueue(task_id)

    def list_tasks(self, session: Session) -> list[TaskResponse]:
        records = session.scalars(
            select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(100)
        ).all()
        return [self.get(session, record.id) for record in records]

    def get(self, session: Session, task_id: str) -> TaskResponse:
        record = session.get(TaskRecord, task_id)
        if record is None:
            raise AssetError("TASK_NOT_FOUND", "找不到该处理任务。", 404)
        artifacts = session.scalars(
            select(ArtifactRecord).where(ArtifactRecord.task_id == task_id)
        ).all()
        plan = session.get(PlanRecord, record.plan_id)
        error = None
        if record.error_json:
            payload = json.loads(record.error_json)
            error = ErrorBody(
                code=payload["code"], message=payload["message"], request_id="worker"
            )
        responses = [self._artifact_response(item) for item in artifacts]
        responses.sort(key=lambda item: (_role_order(item.role), item.page_number or 0))
        comparison = self._comparison(record, plan, responses)
        return TaskResponse(
            id=record.id,
            plan_id=record.plan_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            created_at=record.created_at,
            updated_at=record.updated_at,
            error=error,
            artifacts=responses,
            comparison=comparison,
        )

    def _artifact_response(self, item: ArtifactRecord) -> ArtifactResponse:
        role, page_number = _artifact_role(item)
        return ArtifactResponse(
            id=item.id,
            display_name=item.display_name,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            download_url=f"/api/v1/tasks/{item.task_id}/artifacts/{item.id}",
            role=role,
            page_number=page_number,
        )

    def _comparison(
        self,
        task: TaskRecord,
        plan: PlanRecord | None,
        artifacts: list[ArtifactResponse],
    ) -> ComparisonResponse | None:
        if plan is None:
            return None
        payload = json.loads(plan.plan_json)
        if payload.get("response", {}).get("output_kind") == "png":
            return None
        candidates = payload.get("candidates", [])
        regions = payload.get("regions", [])
        source_pages = {
            item.page_number: item
            for item in artifacts
            if item.role == "source_preview" and item.page_number is not None
        }
        result_pages = {
            item.page_number: item
            for item in artifacts
            if item.role == "result_preview" and item.page_number is not None
        }
        page_numbers = sorted(set(source_pages) | set(result_pages))
        available = bool(source_pages and result_pages)
        warning = None
        if task.status == "succeeded" and not available:
            output_kind = payload.get("response", {}).get("output_kind", "docx")
            warning = f"未能生成页面预览；无水印 {output_kind.upper()} 仍可正常下载。"
        changed_parts = set()
        for item in candidates:
            locator = item["source_locator"]
            if locator.get("part_name"):
                changed_parts.add(locator["part_name"])
            changed_parts.update(f"page:{page}" for page in locator.get("page_numbers", []))
        changed_parts.update(f"page:{item['page_number']}" for item in regions)
        return ComparisonResponse(
            available=available,
            removed_count=(
                len(regions) if payload.get("kind") == "pdf_redaction" else len(candidates)
            ),
            changed_parts=sorted(changed_parts),
            source_page_count=len(source_pages),
            result_page_count=len(result_pages),
            pages=[
                ComparisonPage(
                    page_number=page_number,
                    source_url=(
                        source_pages[page_number].download_url
                        if page_number in source_pages
                        else None
                    ),
                    result_url=(
                        result_pages[page_number].download_url
                        if page_number in result_pages
                        else None
                    ),
                )
                for page_number in page_numbers
            ],
            warning=warning,
        )

    def artifact_path(
        self, session: Session, task_id: str, artifact_id: str
    ) -> tuple[Path, str, str, bool]:
        record = session.scalar(
            select(ArtifactRecord).where(
                ArtifactRecord.id == artifact_id, ArtifactRecord.task_id == task_id
            )
        )
        if record is None:
            raise AssetError("ARTIFACT_NOT_FOUND", "找不到该输出文件。", 404)
        path = (self.assets.data_dir / record.relative_path).resolve()
        if self.assets.data_dir not in path.parents or not path.is_file():
            raise AssetError("STORAGE_ERROR", "输出文件路径校验失败。", 500)
        role, _ = _artifact_role(record)
        return path, record.display_name, record.media_type, role == "output"

    def _remove_task_files(self, task_id: str) -> None:
        shutil.rmtree(self.artifact_root / task_id, ignore_errors=True)


def _artifact_role(item: ArtifactRecord) -> tuple[str, int | None]:
    path = Path(item.relative_path)
    if item.media_type != "image/png" or path.parent.name not in {"source", "result"}:
        return "output", None
    side = path.parent.name
    role = "source_preview" if side == "source" else "result_preview"
    try:
        page_number = int(path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        page_number = None
    return role, page_number


def _role_order(role: str) -> int:
    return {"output": 0, "source_preview": 1, "result_preview": 2}[role]
