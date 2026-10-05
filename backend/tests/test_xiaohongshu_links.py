from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wmrm.adapters.xiaohongshu.links import (
    MetadataResponse,
    XiaohongshuLinkError,
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
