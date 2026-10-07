import os
from concurrent.futures import CancelledError
from pathlib import Path
from typing import Any, cast

from wmrm.adapters.documents.docx_editor import remove_docx_candidates
from wmrm.adapters.documents.docx_preview import DocxPreviewRenderer
from wmrm.adapters.images.inpaint import inpaint_image
from wmrm.adapters.pdf.codecv_editor import remove_codecv_candidates
from wmrm.adapters.pdf.preview import PdfPreviewRenderer
from wmrm.adapters.pdf.pymupdf_redaction import LicenseMode, redact_pdf_regions
from wmrm.adapters.pdf.raster_inpaint import raster_inpaint_pdf_regions


def run_task_process(request: dict[str, Any], result_queue: Any, cancel_event: Any) -> None:
    """Run one document job in an isolated child process."""
    try:
        asset_kind = str(request["asset_kind"])
        source_path = Path(request["source_path"])
        output_path = Path(request["output_path"])
        preview_path = Path(request["preview_path"])
        plan_kind = str(request.get("plan_kind", "object_removal"))
        if asset_kind in {"png", "jpeg", "webp"}:
            result = inpaint_image(
                source_path,
                output_path,
                list(request["regions"]),
                int(request["radius"]),
                cancel_event.is_set,
            )
            preview_payload = {"available": False, "warning": None, "images": []}
        elif plan_kind in {"pdf_redaction", "pdf_raster_inpaint"}:
            if plan_kind == "pdf_raster_inpaint":
                result = raster_inpaint_pdf_regions(
                    source_path,
                    output_path,
                    list(request["regions"]),
                    license_mode=cast(LicenseMode, str(request["license_mode"])),
                    dpi=int(request["dpi"]),
                    radius=int(request["radius"]),
                    ocr_languages=str(request["ocr_languages"]),
                    should_cancel=cancel_event.is_set,
                )
            else:
                result = redact_pdf_regions(
                    source_path,
                    output_path,
                    list(request["regions"]),
                    license_mode=cast(LicenseMode, str(request["license_mode"])),
                    should_cancel=cancel_event.is_set,
                )
            renderer = _renderer(asset_kind, request["preview_config"])
            preview = renderer.render(
                source_path,
                output_path,
                preview_path,
                cancel_event.is_set,
            )
            preview_payload = _preview_payload(preview)
        else:
            candidates = list(request["candidates"])
            processor = remove_codecv_candidates if asset_kind == "pdf" else remove_docx_candidates
            renderer = _renderer(asset_kind, request["preview_config"])
            result = processor(
                source_path,
                output_path,
                candidates,
                cancel_event.is_set,
            )
            preview = renderer.render(
                source_path,
                output_path,
                preview_path,
                cancel_event.is_set,
            )
            preview_payload = _preview_payload(preview)
        if cancel_event.is_set():
            raise CancelledError("任务已取消。")
        result_queue.put(
            {
                "status": "succeeded",
                "worker_pid": os.getpid(),
                "result": result,
                "preview": preview_payload,
            }
        )
    except CancelledError:
        result_queue.put({"status": "cancelled", "worker_pid": os.getpid()})
    except BaseException as exc:
        result_queue.put(
            {
                "status": "failed",
                "worker_pid": os.getpid(),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


def _renderer(asset_kind: str, config: dict[str, Any]):
    renderer_type = PdfPreviewRenderer if asset_kind == "pdf" else DocxPreviewRenderer
    return renderer_type(
        enabled=bool(config["enabled"]),
        dpi=int(config["dpi"]),
        max_pages=int(config["max_pages"]),
        timeout_seconds=int(config["timeout_seconds"]),
    )


def _preview_payload(preview) -> dict[str, Any]:
    return {
        "available": preview.available,
        "warning": preview.warning,
        "images": [
            {
                "side": image.side,
                "page_number": image.page_number,
                "path": str(image.path),
                "size_bytes": image.size_bytes,
                "sha256": image.sha256,
            }
            for image in preview.images
        ],
    }
