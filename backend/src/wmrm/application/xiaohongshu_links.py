from wmrm.adapters.xiaohongshu.links import (
    DownloadedImage,
    MediaTransport,
    MetadataTransport,
    PublicHttpsTransport,
    PublicMediaTransport,
    XiaohongshuLinkError,
    download_image,
    parse_share_text,
    resolve_metadata,
)


class XiaohongshuLinkService:
    def __init__(
        self,
        *,
        metadata_enabled: bool,
        media_import_enabled: bool,
        timeout_seconds: float,
        max_bytes: int,
        media_max_bytes: int,
        max_redirects: int,
        transport: MetadataTransport | None = None,
        media_transport: MediaTransport | None = None,
    ) -> None:
        self.metadata_enabled = metadata_enabled
        self.media_import_enabled = media_import_enabled
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.media_max_bytes = media_max_bytes
        self.max_redirects = max_redirects
        self.transport = transport or PublicHttpsTransport()
        self.media_transport = media_transport or PublicMediaTransport()

    def preview(self, share_text: str, resolve: bool) -> dict[str, object]:
        parsed = parse_share_text(share_text)
        result: dict[str, object] = {
            "kind": parsed.kind,
            "normalized_url": parsed.normalized_url,
            "canonical_url": parsed.normalized_url if parsed.kind == "direct" else None,
            "note_id": parsed.note_id,
            "metadata_status": "not_requested",
            "title": None,
            "description": None,
            "author": None,
            "thumbnail_present": False,
            "media_download_supported": self.metadata_enabled and self.media_import_enabled,
            "media_candidates": [],
            "warnings": [],
        }
        if not resolve:
            return result
        if not self.metadata_enabled:
            result["metadata_status"] = "disabled"
            result["warnings"] = ["页面元数据读取默认关闭；可由本机管理员显式启用。"]
            return result
        try:
            metadata = resolve_metadata(
                parsed,
                self.transport,
                timeout=self.timeout_seconds,
                max_bytes=self.max_bytes,
                max_redirects=self.max_redirects,
            )
        except XiaohongshuLinkError as exc:
            if exc.code in {"XHS_HOST_NOT_ALLOWED", "XHS_HTTPS_REQUIRED", "XHS_UNSAFE_ADDRESS"}:
                raise
            result["metadata_status"] = "unavailable"
            result["warnings"] = [exc.message]
            return result
        result.update(
            {
                "canonical_url": metadata.canonical_url,
                "note_id": metadata.note_id,
                "metadata_status": "resolved",
                "title": metadata.title,
                "description": metadata.description,
                "author": metadata.author,
                "thumbnail_present": metadata.thumbnail_present,
                "media_candidates": [
                    {
                        "candidate_id": candidate.candidate_id,
                        "position": candidate.position,
                        "role": candidate.role,
                    }
                    for candidate in metadata.media_candidates
                ],
                "warnings": list(metadata.warnings),
            }
        )
        return result

    def import_image(self, share_text: str, candidate_id: str) -> DownloadedImage:
        if not self.metadata_enabled or not self.media_import_enabled:
            raise XiaohongshuLinkError(
                "XHS_MEDIA_IMPORT_DISABLED",
                "小红书图片导入未由本机管理员启用。",
                409,
            )
        parsed = parse_share_text(share_text)
        metadata = resolve_metadata(
            parsed,
            self.transport,
            timeout=self.timeout_seconds,
            max_bytes=self.max_bytes,
            max_redirects=self.max_redirects,
        )
        candidate = next(
            (item for item in metadata.media_candidates if item.candidate_id == candidate_id),
            None,
        )
        if candidate is None:
            raise XiaohongshuLinkError(
                "XHS_MEDIA_CANDIDATE_NOT_FOUND",
                "页面已变化或图片候选不存在，请重新预览。",
                409,
            )
        return download_image(
            candidate,
            self.media_transport,
            timeout=self.timeout_seconds,
            max_bytes=self.media_max_bytes,
            max_redirects=self.max_redirects,
        )
