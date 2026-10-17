import base64
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR42mP8z8Dwn4GBgYGJAQoAHgQCAftB5gAAAABJRU5ErkJggg=="
)


def make_drawingml_docx(
    *,
    media: bytes = PNG,
    media_name: str = "watermark.png",
    external: bool = False,
) -> bytes:
    relationship = (
        '<Relationship Id="rIdImage" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="https://example.invalid/{media_name}" TargetMode="External"/>'
        if external
        else (
            '<Relationship Id="rIdImage" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="media/{media_name}"/>'
        )
    )
    header = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<w:p><w:r><w:drawing><wp:anchor behindDoc="1">'
        '<wp:extent cx="1905000" cy="952500"/>'
        '<wp:docPr id="1" name="Watermark picture" descr="DRAFT overlay"/>'
        '<a:graphic><a:graphicData><pic:pic>'
        '<pic:nvPicPr><pic:cNvPr id="2" name="watermark.png"/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="rIdImage"/></pic:blipFill>'
        '</pic:pic></a:graphicData></a:graphic>'
        '</wp:anchor></w:drawing></w:r></w:p></w:hdr>'
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types '
            'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        package.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body/></w:document>',
        )
        package.writestr("word/header1.xml", header)
        package.writestr(
            "word/_rels/header1.xml.rels",
            '<?xml version="1.0"?><Relationships '
            'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{relationship}</Relationships>",
        )
        if not external:
            package.writestr(f"word/media/{media_name}", media)
    return output.getvalue()


def _scan(client: TestClient, source: bytes) -> tuple[dict, dict]:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("drawing-watermark.docx", source)},
    )
    assert uploaded.status_code == 201
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"], "watermark_text": "DRAFT"},
    )
    assert analysis.status_code == 201
    return uploaded.json(), analysis.json()


def test_scans_drawingml_image_as_read_only_candidate_with_safe_preview(client: TestClient) -> None:
    _, analysis = _scan(client, make_drawingml_docx())

    assert len(analysis["candidates"]) == 1
    candidate = analysis["candidates"][0]
    assert candidate["kind"] == "image"
    assert candidate["classification"] == "ambiguous"
    assert candidate["allowed_strategies"] == []
    assert candidate["content"] == "DRAFT overlay · Watermark picture · watermark.png"
    assert candidate["source_locator"]["drawing_index"] == 0
    assert candidate["source_locator"]["relationship_id"] == "rIdImage"
    assert candidate["source_locator"]["media_part_name"] == "word/media/watermark.png"
    assert candidate["source_locator"]["media_sha256"]
    assert candidate["preview_media_type"] == "image/png"
    assert candidate["preview_url"].endswith(f"/{candidate['candidate_id']}/preview")
    assert "图片位于正文后方" in candidate["evidence"]

    preview = client.get(candidate["preview_url"])
    assert preview.status_code == 200
    assert preview.content == PNG
    assert preview.headers["content-type"] == "image/png"
    assert preview.headers["cache-control"] == "no-store"
    assert preview.headers["x-content-type-options"] == "nosniff"


def test_drawingml_image_candidate_cannot_enter_object_removal_plan(
    client: TestClient,
) -> None:
    asset, analysis = _scan(client, make_drawingml_docx())
    candidate = analysis["candidates"][0]

    response = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": asset["id"],
            "asset_sha256": asset["sha256"],
            "analysis_id": analysis["id"],
            "operations": [
                {"candidate_id": candidate["candidate_id"], "strategy": "object"}
            ],
            "acknowledged_warnings": [
                f"AMBIGUOUS_CANDIDATE:{candidate['candidate_id']}"
            ],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PLAN"


def test_external_drawingml_image_is_not_fetched(client: TestClient) -> None:
    _, analysis = _scan(client, make_drawingml_docx(external=True))

    assert analysis["candidates"] == []
    assert any("外部图片关系" in warning for warning in analysis["warnings"])


def test_unsupported_embedded_image_is_listed_without_browser_preview(
    client: TestClient,
) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><text>DRAFT</text></svg>'
    _, analysis = _scan(
        client,
        make_drawingml_docx(media=svg, media_name="watermark.svg"),
    )

    candidate = analysis["candidates"][0]
    assert candidate["kind"] == "image"
    assert candidate["preview_url"] is None
    assert candidate["preview_media_type"] is None
    assert "不能在浏览器中安全预览" in candidate["evidence"]


def test_preview_rejects_unknown_candidate(client: TestClient) -> None:
    _, analysis = _scan(client, make_drawingml_docx())

    response = client.get(
        f"/api/v1/analyses/{analysis['id']}/candidates/missing/preview"
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CANDIDATE_NOT_FOUND"
