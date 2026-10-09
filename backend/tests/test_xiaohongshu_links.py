from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import wmrm.adapters.xiaohongshu.links as xhs_links
from wmrm.adapters.xiaohongshu.links import (
    MediaCandidate,
    MetadataResponse,
    PublicHttpsTransport,
    PublicMediaTransport,
    XiaohongshuLinkError,
    download_image,
    parse_share_text,
    resolve_metadata,
)
from wmrm.api.app import create_app
from wmrm.settings import Settings

NOTE_ID = "66aabbccddeeff0011223344"


class FakeTransport:
    def __init__(self, responses: list[MetadataResponse]):
        self.responses = responses
        self.urls: list[str] = []

    def fetch(self, url: str, *, timeout: float, max_bytes: int) -> MetadataResponse:
        assert timeout > 0
        assert max_bytes >= 1024
        self.urls.append(url)
        return self.responses.pop(0)


class FakeHttpResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str):
        self.body = body
        self.content_type = content_type

    def read(self, limit: int) -> bytes:
        return self.body[:limit]

    def getheaders(self) -> list[tuple[str, str]]:
        return [("Content-Type", self.content_type)]


def test_parses_direct_note_and_removes_query_from_public_result() -> None:
    parsed = parse_share_text(
        f"复制打开小红书 https://www.xiaohongshu.com/explore/{NOTE_ID}?xsec_token=secret#reply"
    )

    assert parsed.kind == "direct"
    assert parsed.note_id == NOTE_ID
    assert parsed.normalized_url == f"https://www.xiaohongshu.com/explore/{NOTE_ID}"
    assert "xsec_token=secret" in parsed.request_url
    assert "#reply" not in parsed.request_url


def test_parses_short_share_link_from_text() -> None:
    parsed = parse_share_text("发现一篇笔记 https://xhslink.com/aBcD12EF，复制后打开")

    assert parsed.kind == "short"
    assert parsed.note_id is None
    assert parsed.normalized_url == "https://xhslink.com/aBcD12EF"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("没有链接", "XHS_LINK_NOT_FOUND"),
        (f"http://www.xiaohongshu.com/explore/{NOTE_ID}", "XHS_HTTPS_REQUIRED"),
        (f"https://evil.example/explore/{NOTE_ID}", "XHS_HOST_NOT_ALLOWED"),
        (f"https://xiaohongshu.com.evil.example/explore/{NOTE_ID}", "XHS_HOST_NOT_ALLOWED"),
        (f"https://user@www.xiaohongshu.com/explore/{NOTE_ID}", "XHS_LINK_INVALID"),
        ("https://xhslink.com/", "XHS_LINK_INVALID"),
        (
            f"https://www.xiaohongshu.com/explore/{NOTE_ID} https://xhslink.com/aBcD12EF",
            "XHS_MULTIPLE_LINKS",
        ),
    ],
)
def test_rejects_invalid_or_ambiguous_input(value: str, code: str) -> None:
    with pytest.raises(XiaohongshuLinkError) as error:
        parse_share_text(value)
    assert error.value.code == code


@pytest.mark.parametrize(
    "proxy_url",
    [
        "https://127.0.0.1:7890",
        "http://localhost:7890",
        "http://192.168.1.2:7890",
        "http://user@127.0.0.1:7890",
        "http://127.0.0.1:7890/proxy",
        "http://127.0.0.1",
    ],
)
def test_rejects_non_loopback_or_ambiguous_https_proxy(proxy_url: str) -> None:
    with pytest.raises(ValueError, match="小红书 HTTPS 代理"):
        PublicHttpsTransport(proxy_url)


def test_accepts_ipv4_and_ipv6_loopback_https_proxies() -> None:
    assert PublicHttpsTransport("http://127.0.0.1:7890").proxy is not None
    assert PublicMediaTransport("http://[::1]:7890").proxy is not None


def test_proxy_transport_tunnels_allowlisted_host_without_local_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    class FakeConnection:
        def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
            calls.update(method=method, target=target, headers=headers)

        def getresponse(self) -> FakeHttpResponse:
            return FakeHttpResponse(b"<title>Proxy result</title>", "text/html")

        def close(self) -> None:
            calls["closed"] = True

    def connection_factory(proxy, host: str, *, timeout: float):
        calls.update(proxy_host=proxy.host, proxy_port=proxy.port, host=host, timeout=timeout)
        return FakeConnection()

    def fail_dns(_: str) -> str:
        raise AssertionError("proxy mode must not use fake-IP local DNS")

    monkeypatch.setattr(xhs_links, "_LoopbackProxyHTTPSConnection", connection_factory)
    monkeypatch.setattr(xhs_links, "_resolve_public_ip", fail_dns)
    response = PublicHttpsTransport("http://127.0.0.1:7890").fetch(
        f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
        timeout=2,
        max_bytes=100_000,
    )

    assert response.status == 200
    assert calls == {
        "proxy_host": "127.0.0.1",
        "proxy_port": 7890,
        "host": "www.xiaohongshu.com",
        "timeout": 2,
        "method": "GET",
        "target": f"/explore/{NOTE_ID}",
        "headers": {
            "Accept": "text/html,application/xhtml+xml",
            "Host": "www.xiaohongshu.com",
            "User-Agent": "wmrm-metadata-preview/0.1",
        },
        "closed": True,
    }


def test_resolves_short_link_to_metadata_without_returning_media_url() -> None:
    image_url = "https://sns-webpic-qc.xhscdn.com/private-image.jpg"
    transport = FakeTransport(
        [
            MetadataResponse(
                302,
                {"location": f"https://www.xiaohongshu.com/explore/{NOTE_ID}?source=share"},
                b"",
            ),
            MetadataResponse(
                200,
                {"content-type": "text/html; charset=utf-8"},
                (
                    "<html><head>"
                    '<meta property="og:title" content="城市散步路线">'
                    '<meta property="og:description" content=" 周末 城市散步 ">'
                    '<meta name="author" content="示例作者">'
                    f'<meta property="og:image" content="{image_url}">'
                    f'<link rel="canonical" href="/explore/{NOTE_ID}">'
                    "</head></html>"
                ).encode(),
            ),
        ]
    )

    metadata = resolve_metadata(
        parse_share_text("https://xhslink.com/aBcD12EF"),
        transport,
        timeout=2,
        max_bytes=100_000,
        max_redirects=3,
    )

    assert metadata.canonical_url == f"https://www.xiaohongshu.com/explore/{NOTE_ID}"
    assert metadata.note_id == NOTE_ID
    assert metadata.title == "城市散步路线"
    assert metadata.description == "周末 城市散步"
    assert metadata.author == "示例作者"
    assert metadata.thumbnail_present is True
    assert len(metadata.media_candidates) == 1
    assert metadata.media_candidates[0].candidate_id.startswith("xhs-image-")
    assert image_url not in repr(metadata)


def test_rejects_redirect_outside_allowlist() -> None:
    transport = FakeTransport(
        [MetadataResponse(302, {"location": "https://evil.example/collect"}, b"")]
    )
    with pytest.raises(XiaohongshuLinkError) as error:
        resolve_metadata(
            parse_share_text("https://xhslink.com/aBcD12EF"),
            transport,
            timeout=2,
            max_bytes=100_000,
            max_redirects=3,
        )
    assert error.value.code == "XHS_HOST_NOT_ALLOWED"


def test_rejects_non_html_metadata_response() -> None:
    transport = FakeTransport(
        [MetadataResponse(200, {"content-type": "application/octet-stream"}, b"payload")]
    )
    with pytest.raises(XiaohongshuLinkError) as error:
        resolve_metadata(
            parse_share_text(f"https://www.xiaohongshu.com/explore/{NOTE_ID}"),
            transport,
            timeout=2,
            max_bytes=100_000,
            max_redirects=3,
        )
    assert error.value.code == "XHS_CONTENT_TYPE_UNSUPPORTED"


def test_media_redirect_cannot_leave_xiaohongshu_cdn() -> None:
    candidate = MediaCandidate(
        candidate_id="xhs-image-0123456789abcdef0123",
        position=1,
        role="cover",
        source_url="https://sns-webpic-qc.xhscdn.com/cover.png",
    )
    transport = FakeTransport(
        [MetadataResponse(302, {"location": "https://evil.example/cover.png"}, b"")]
    )

    with pytest.raises(XiaohongshuLinkError) as error:
        download_image(
            candidate,
            transport,
            timeout=2,
            max_bytes=100_000,
            max_redirects=3,
        )

    assert error.value.code == "XHS_MEDIA_HOST_NOT_ALLOWED"


def test_media_download_rejects_unsupported_content_type() -> None:
    candidate = MediaCandidate(
        candidate_id="xhs-image-0123456789abcdef0123",
        position=1,
        role="cover",
        source_url="https://sns-webpic-qc.xhscdn.com/cover.bin",
    )
    transport = FakeTransport(
        [MetadataResponse(200, {"content-type": "application/octet-stream"}, b"data")]
    )

    with pytest.raises(XiaohongshuLinkError) as error:
        download_image(
            candidate,
            transport,
            timeout=2,
            max_bytes=100_000,
            max_redirects=3,
        )

    assert error.value.code == "XHS_MEDIA_TYPE_UNSUPPORTED"


def test_preview_api_parses_without_network(client: TestClient) -> None:
    response = client.post(
        "/api/v1/xiaohongshu/preview",
        json={"share_text": f"看看这篇 https://www.xiaohongshu.com/explore/{NOTE_ID}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "kind": "direct",
        "normalized_url": f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
        "canonical_url": f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
        "note_id": NOTE_ID,
        "metadata_status": "not_requested",
        "title": None,
        "description": None,
        "author": None,
        "thumbnail_present": False,
        "media_download_supported": False,
        "media_candidates": [],
        "warnings": [],
    }


def test_preview_api_reports_metadata_disabled(client: TestClient) -> None:
    response = client.post(
        "/api/v1/xiaohongshu/preview",
        json={
            "share_text": "https://xhslink.com/aBcD12EF",
            "resolve_metadata": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["metadata_status"] == "disabled"
    assert response.json()["media_download_supported"] is False


def test_preview_api_resolves_with_explicit_opt_in(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            MetadataResponse(
                200,
                {"content-type": "text/html"},
                b'<meta property="og:title" content="A safe preview">',
            )
        ]
    )
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            docx_preview_enabled=False,
            pdf_preview_enabled=False,
            worker_start_method="forkserver",
            xhs_metadata_enabled=True,
        ),
        xiaohongshu_transport=transport,
    )
    with TestClient(app) as api:
        response = api.post(
            "/api/v1/xiaohongshu/preview",
            json={
                "share_text": f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
                "resolve_metadata": True,
            },
        )

    assert response.status_code == 200
    assert response.json()["metadata_status"] == "resolved"
    assert response.json()["title"] == "A safe preview"
    assert set(response.json()).isdisjoint({"media_urls", "image_url", "video_url"})


def test_preview_ignores_media_url_outside_xiaohongshu_cdn() -> None:
    transport = FakeTransport(
        [
            MetadataResponse(
                200,
                {"content-type": "text/html"},
                b'<meta property="og:image" content="https://evil.example/tracker.png">',
            )
        ]
    )
    metadata = resolve_metadata(
        parse_share_text(f"https://www.xiaohongshu.com/explore/{NOTE_ID}"),
        transport,
        timeout=2,
        max_bytes=100_000,
        max_redirects=3,
    )

    assert metadata.media_candidates == ()
    assert metadata.thumbnail_present is False
    assert metadata.warnings == ("页面提供了不受支持的图片地址，已忽略。",)


def test_extracts_page_declared_gallery_and_upgrades_cdn_urls_to_https() -> None:
    first = "http://sns-webpic-qc.xhscdn.com/first.jpg?token=one"
    second = "http://sns-webpic-qc.xhscdn.com/second.jpg?token=two"
    transport = FakeTransport(
        [
            MetadataResponse(
                200,
                {"content-type": "text/html"},
                (
                    '<meta property="og:image" content="//picasso-static.xiaohongshu.com/logo.png">'
                    f'<meta property="og:image" content="{first}">'
                    f'<meta property="og:image" content="{second}">'
                    f'<meta property="og:image" content="{second}">'
                ).encode(),
            )
        ]
    )

    metadata = resolve_metadata(
        parse_share_text(f"https://www.xiaohongshu.com/explore/{NOTE_ID}"),
        transport,
        timeout=2,
        max_bytes=100_000,
        max_redirects=3,
    )

    assert [(item.position, item.role) for item in metadata.media_candidates] == [
        (1, "cover"),
        (2, "gallery"),
    ]
    assert metadata.media_candidates[0].source_url == first.replace("http://", "https://")
    assert metadata.media_candidates[1].source_url == second.replace("http://", "https://")
    assert metadata.warnings == ("页面提供了不受支持的图片地址，已忽略。",)


def test_imports_previewed_cover_into_local_asset_store(tmp_path: Path) -> None:
    media_url = "https://sns-webpic-qc.xhscdn.com/public-cover.png?token=secret"
    html = f'<meta property="og:image" content="{media_url}">'.encode()
    metadata_transport = FakeTransport(
        [
            MetadataResponse(200, {"content-type": "text/html"}, html),
            MetadataResponse(200, {"content-type": "text/html"}, html),
        ]
    )
    image_buffer = BytesIO()
    Image.new("RGB", (12, 8), "#d04a3a").save(image_buffer, format="PNG")
    media_transport = FakeTransport(
        [
            MetadataResponse(
                200,
                {"content-type": "image/png"},
                image_buffer.getvalue(),
            )
        ]
    )
    app = create_app(
        Settings(
            data_dir=tmp_path / "data",
            docx_preview_enabled=False,
            pdf_preview_enabled=False,
            worker_start_method="forkserver",
            xhs_metadata_enabled=True,
            xhs_media_import_enabled=True,
        ),
        xiaohongshu_transport=metadata_transport,
        xiaohongshu_media_transport=media_transport,
    )
    share_text = f"https://www.xiaohongshu.com/explore/{NOTE_ID}"
    with TestClient(app) as api:
        preview = api.post(
            "/api/v1/xiaohongshu/preview",
            json={"share_text": share_text, "resolve_metadata": True},
        )
        candidate = preview.json()["media_candidates"][0]
        imported = api.post(
            "/api/v1/xiaohongshu/import",
            json={"share_text": share_text, "candidate_id": candidate["candidate_id"]},
        )
        content = api.get(f"/api/v1/assets/{imported.json()['id']}/content")

    assert preview.status_code == 200
    assert preview.json()["media_download_supported"] is True
    assert media_url not in preview.text
    assert imported.status_code == 201
    assert imported.json()["kind"] == "png"
    assert imported.json()["display_name"] == "xiaohongshu-1.png"
    assert content.content == image_buffer.getvalue()


def test_rejects_media_import_when_local_opt_in_is_disabled(client: TestClient) -> None:
    response = client.post(
        "/api/v1/xiaohongshu/import",
        json={
            "share_text": f"https://www.xiaohongshu.com/explore/{NOTE_ID}",
            "candidate_id": "xhs-image-0123456789abcdef0123",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "XHS_MEDIA_IMPORT_DISABLED"
