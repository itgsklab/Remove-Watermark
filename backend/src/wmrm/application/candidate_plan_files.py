from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from wmrm.adapters.documents.docx import DocxInspector
from wmrm.adapters.pdf.codecv import CodeCvPdfInspector
from wmrm.api.schemas import CandidateResponse, PlanWarning, SourceLocator
from wmrm.application.assets import AssetError, detect_kind
from wmrm.settings import Settings

MAX_PLAN_BYTES = 4 * 1024 * 1024


class CandidatePlanFileError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CandidatePlanFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    kind: Literal["docx_object_removal", "codecv_object_removal"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_size_bytes: int = Field(gt=0)
    source_kind: Literal["docx", "pdf"]
    watermark_text: str | None = Field(default=None, max_length=200)
    inspected_parts: list[str]
    scan_warnings: list[str]
    match_status: Literal["matched", "needs_review", "not_found"] | None = None
    candidates: list[CandidateResponse]
    warnings: list[PlanWarning]
    plan_id: str = Field(pattern=r"^[0-9a-f]{64}$")


def create_candidate_plan(
    source: Path,
    plan_kind: Literal["docx", "codecv"],
    *,
    watermark_text: str | None = None,
    settings: Settings | None = None,
) -> CandidatePlanFile:
    config = settings or Settings()
    if watermark_text is not None:
        watermark_text = watermark_text.strip()
        if not watermark_text or len(watermark_text) > 200:
            raise CandidatePlanFileError(
                "WATERMARK_TEXT_INVALID",
                "Watermark text must contain 1 to 200 characters.",
            )
    try:
        size_bytes = source.stat().st_size
        if size_bytes <= 0 or size_bytes > config.max_upload_bytes:
            raise CandidatePlanFileError(
                "DOCUMENT_RESOURCE_LIMIT",
                f"Document must contain 1 to {config.max_upload_bytes} bytes.",
            )
        digest = _sha256(source)
        with source.open("rb") as handle:
            asset_kind, _ = detect_kind(handle.read(32), source.name)
        expected_kind = "docx" if plan_kind == "docx" else "pdf"
        if asset_kind.value != expected_kind:
            raise CandidatePlanFileError(
                "DOCUMENT_INPUT_INVALID",
                f"{plan_kind} plan requires a {expected_kind.upper()} source.",
            )

        if plan_kind == "docx":
            inspection = DocxInspector(
                config.max_docx_entries, config.max_docx_uncompressed_bytes
            ).inspect(source, digest, watermark_text)
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
            scan_warnings = list(inspection.warnings)
            match_status = None
            kind = "docx_object_removal"
        else:
            inspection = CodeCvPdfInspector(
                config.max_pdf_pages, config.max_pdf_content_bytes
            ).inspect(source, digest)
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
            scan_warnings = list(inspection.warnings)
            match_status = inspection.match_status
            kind = "codecv_object_removal"
    except CandidatePlanFileError:
        raise
    except AssetError as exc:
        raise CandidatePlanFileError(exc.code, str(exc)) from exc
    except OSError as exc:
        raise CandidatePlanFileError(
            "DOCUMENT_INPUT_INVALID", "Document could not be read."
        ) from exc

    warnings = [
        PlanWarning(
            code=f"AMBIGUOUS_CANDIDATE:{item.candidate_id}",
            candidate_id=item.candidate_id,
            message="该候选证据不足，删除前需要人工核对并明确确认。",
        )
        for item in candidates
        if item.classification == "ambiguous"
    ]
    payload = {
        "schema_version": 1,
        "kind": kind,
        "source_sha256": digest,
        "source_size_bytes": size_bytes,
        "source_kind": asset_kind.value,
        "watermark_text": watermark_text,
        "inspected_parts": inspected_parts,
        "scan_warnings": scan_warnings,
        "match_status": match_status,
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "warnings": [item.model_dump(mode="json") for item in warnings],
    }
    return CandidatePlanFile(**payload, plan_id=_payload_digest(payload))


def load_candidate_plan(path: Path) -> CandidatePlanFile:
    try:
        size = path.stat().st_size
        if size <= 0 or size > MAX_PLAN_BYTES:
            raise CandidatePlanFileError(
                "DOCUMENT_PLAN_INVALID", "Document plan size is invalid."
            )
        plan = CandidatePlanFile.model_validate_json(path.read_text(encoding="utf-8"))
    except CandidatePlanFileError:
        raise
    except (OSError, UnicodeError, ValidationError, ValueError) as exc:
        raise CandidatePlanFileError(
            "DOCUMENT_PLAN_INVALID", "Document plan is missing or malformed."
        ) from exc
    expected = _payload_digest(plan.model_dump(mode="json", exclude={"plan_id"}))
    if plan.plan_id != expected:
        raise CandidatePlanFileError(
            "DOCUMENT_PLAN_INTEGRITY_FAILED",
            "Document plan content does not match its plan ID.",
        )
    return plan


def revalidate_candidate_plan(source: Path, plan: CandidatePlanFile) -> CandidatePlanFile:
    plan_kind: Literal["docx", "codecv"] = (
        "docx" if plan.kind == "docx_object_removal" else "codecv"
    )
    fresh = create_candidate_plan(
        source,
        plan_kind,
        watermark_text=plan.watermark_text,
    )
    if fresh.model_dump(mode="json") != plan.model_dump(mode="json"):
        raise CandidatePlanFileError(
            "DOCUMENT_PLAN_STALE",
            "Document content or candidate evidence has changed; create a new plan.",
        )
    return fresh


def select_candidates(
    plan: CandidatePlanFile,
    candidate_ids: list[str],
    acknowledged_warnings: list[str],
) -> list[CandidateResponse]:
    if not candidate_ids:
        raise CandidatePlanFileError(
            "DOCUMENT_CANDIDATE_REQUIRED", "Select at least one candidate."
        )
    if len(set(candidate_ids)) != len(candidate_ids):
        raise CandidatePlanFileError(
            "DOCUMENT_CANDIDATE_INVALID", "Candidate selection contains duplicates."
        )
    by_id = {item.candidate_id: item for item in plan.candidates}
    try:
        selected = [by_id[item] for item in candidate_ids]
    except KeyError as exc:
        raise CandidatePlanFileError(
            "DOCUMENT_CANDIDATE_INVALID", f"Unknown candidate ID: {exc.args[0]}"
        ) from exc
    if any("object" not in item.allowed_strategies for item in selected):
        raise CandidatePlanFileError(
            "DOCUMENT_CANDIDATE_INVALID", "A selected candidate cannot be removed."
        )

    required = {
        f"AMBIGUOUS_CANDIDATE:{item.candidate_id}"
        for item in selected
        if item.classification == "ambiguous"
    }
    acknowledged = set(acknowledged_warnings)
    unknown = sorted(acknowledged - required)
    if unknown:
        raise CandidatePlanFileError(
            "DOCUMENT_ACKNOWLEDGEMENT_INVALID",
            "Unknown or unselected acknowledgement codes: " + ", ".join(unknown),
        )
    missing = sorted(required - acknowledged)
    if missing:
        raise CandidatePlanFileError(
            "DOCUMENT_ACKNOWLEDGEMENT_REQUIRED",
            "Required acknowledgement codes: " + ", ".join(missing),
        )
    return selected


def serialize_candidate_plan(plan: CandidatePlanFile) -> str:
    return json.dumps(
        plan.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"


def _payload_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
