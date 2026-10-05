from enum import StrEnum


class AssetKind(StrEnum):
    DOCX = "docx"
    PDF = "pdf"
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NEEDS_REVIEW = "needs_review"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"

