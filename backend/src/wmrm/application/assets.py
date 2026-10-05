import hashlib
import os
import re
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from wmrm.domain.enums import AssetKind
from wmrm.domain.models import InspectedFile
from wmrm.persistence.database import AnalysisRecord, AssetRecord


class AssetError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


MAGIC_TYPES: tuple[tuple[bytes, AssetKind, str], ...] = (
    (b"%PDF-", AssetKind.PDF, "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", AssetKind.PNG, "image/png"),
    (b"\xff\xd8\xff", AssetKind.JPEG, "image/jpeg"),
)


def sanitize_display_name(filename: str | None) -> str:
    candidate = Path(filename or "upload.bin").name
    candidate = re.sub(r"[\x00-\x1f\x7f]+", "_", candidate).strip(" .")
    return (candidate or "upload.bin")[:255]


def detect_kind(header: bytes, filename: str) -> tuple[AssetKind, str]:
    for magic, kind, media_type in MAGIC_TYPES:
        if header.startswith(magic):
            return kind, media_type
    if header.startswith(b"PK\x03\x04") and filename.lower().endswith(".docx"):
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return AssetKind.DOCX, media_type
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return AssetKind.WEBP, "image/webp"
    raise AssetError("UNSUPPORTED_FORMAT", "仅支持 DOCX、PDF、PNG、JPEG 和 WebP。", 415)


class AssetService:
    def __init__(self, data_dir: Path, max_upload_bytes: int) -> None:
        self.data_dir = data_dir.resolve()
        self.asset_root = self.data_dir / "assets"
        self.tmp_root = self.data_dir / "tmp"
        self.max_upload_bytes = max_upload_bytes
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.tmp_root.mkdir(parents=True, exist_ok=True)

    async def stage_upload(
        self, chunks: AsyncIterator[bytes], filename: str
    ) -> tuple[str, InspectedFile]:
        asset_id = str(uuid.uuid4())
        temp_path = self.tmp_root / f"{asset_id}.upload"
        digest = hashlib.sha256()
        size = 0
        header = bytearray()
        try:
            with temp_path.open("xb") as output:
                async for chunk in chunks:
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise AssetError(
                            "RESOURCE_LIMIT",
                            f"文件超过 {self.max_upload_bytes} 字节限制。",
                            413,
                        )
                    if len(header) < 32:
                        header.extend(chunk[: 32 - len(header)])
                    digest.update(chunk)
                    output.write(chunk)
            if size == 0:
                raise AssetError("INVALID_FILE", "上传文件为空。")
            kind, media_type = detect_kind(bytes(header), filename)
            target_dir = self.asset_root / asset_id
            target_dir.mkdir(mode=0o700)
            target_path = target_dir / "source.bin"
            os.replace(temp_path, target_path)
            return asset_id, InspectedFile(
                kind=kind,
                media_type=media_type,
                size_bytes=size,
                sha256=digest.hexdigest(),
                stored_path=target_path,
            )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def create_record(
        self,
        session: Session,
        asset_id: str,
        inspected: InspectedFile,
        display_name: str,
    ) -> AssetRecord:
        relative_path = inspected.stored_path.relative_to(self.data_dir).as_posix()
        record = AssetRecord(
            id=asset_id,
            display_name=display_name,
            kind=inspected.kind.value,
            media_type=inspected.media_type,
            size_bytes=inspected.size_bytes,
            sha256=inspected.sha256,
            relative_path=relative_path,
        )
        session.add(record)
        session.commit()
        return record

    def get(self, session: Session, asset_id: str) -> AssetRecord:
        record = session.scalar(select(AssetRecord).where(AssetRecord.id == asset_id))
        if record is None:
            raise AssetError("ASSET_NOT_FOUND", "找不到该文件。", 404)
        return record

    def path_for(self, record: AssetRecord) -> Path:
        path = (self.data_dir / record.relative_path).resolve()
        if self.data_dir not in path.parents:
            raise AssetError("STORAGE_ERROR", "文件路径校验失败。", 500)
        return path

    def delete(self, session: Session, asset_id: str) -> None:
        record = self.get(session, asset_id)
        path = self.path_for(record)
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass
        session.execute(delete(AnalysisRecord).where(AnalysisRecord.asset_id == asset_id))
        session.delete(record)
        session.commit()
