from wmrm.adapters.xiaohongshu.links import (
    MetadataTransport,
    PublicHttpsTransport,
    XiaohongshuLinkError,
    parse_share_text,
    resolve_metadata,
)


class XiaohongshuLinkService:
    def __init__(
        self,
        *,
        metadata_enabled: bool,
        timeout_seconds: float,
        max_bytes: int,
        max_redirects: int,
        transport: MetadataTransport | None = None,
    ) -> None:
        self.metadata_enabled = metadata_enabled
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.transport = transport or PublicHttpsTransport()

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
            "media_download_supported": False,
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
                "warnings": list(metadata.warnings),
            }
        )
        return result
