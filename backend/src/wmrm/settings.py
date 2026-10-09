from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WMRM_", extra="ignore")

    app_name: str = "Watermark Remover"
    app_version: str = "0.1.0rc1"
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path = Field(default=Path(".wmrm-data"))
    max_upload_bytes: int = 100 * 1024 * 1024
    chunk_size: int = 1024 * 1024
    max_docx_entries: int = 2_000
    max_docx_uncompressed_bytes: int = 500 * 1024 * 1024
    max_pdf_pages: int = 200
    max_pdf_content_bytes: int = 50 * 1024 * 1024
    pymupdf_license_mode: Literal["agpl", "commercial"] = "agpl"
    max_image_dimension: int = 20_000
    max_image_pixels: int = 40_000_000
    max_image_frames: int = 100
    pdf_preview_enabled: bool = True
    pdf_preview_dpi: int = 110
    pdf_preview_max_pages: int = 8
    pdf_preview_timeout_seconds: int = 30
    docx_preview_enabled: bool = True
    docx_preview_dpi: int = 110
    docx_preview_max_pages: int = 8
    docx_preview_timeout_seconds: int = 30
    artifact_retention_days: int = 30
    unreferenced_asset_retention_days: int = 7
    failed_work_retention_hours: int = 24
    worker_start_method: Literal["spawn", "forkserver"] = "spawn"
    worker_cancel_grace_seconds: float = Field(default=2.0, ge=0.1, le=30)
    xhs_metadata_enabled: bool = False
    xhs_media_import_enabled: bool = False
    xhs_metadata_timeout_seconds: float = Field(default=5.0, ge=0.5, le=15)
    xhs_metadata_max_bytes: int = Field(default=512 * 1024, ge=1024, le=2 * 1024 * 1024)
    xhs_metadata_max_redirects: int = Field(default=3, ge=0, le=5)
    xhs_media_max_bytes: int = Field(default=25 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    dev_cors: bool = False

    @property
    def database_path(self) -> Path:
        return self.data_dir / "db" / "app.sqlite3"


def load_settings() -> Settings:
    return Settings()
