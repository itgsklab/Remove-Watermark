from io import BytesIO
from time import monotonic, sleep
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient


def make_docx(watermark_text: str | None = None) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        package.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>',
        )
        package.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/officeDocument" '
            'Target="word/document.xml"/>'
            "</Relationships>",
        )
        if watermark_text is not None:
            package.writestr(
                "word/header1.xml",
                (
                    '<?xml version="1.0"?>'
                    '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                    'xmlns:v="urn:schemas-microsoft-com:vml">'
                    '<w:p><w:r><w:pict>'
                    '<v:shape id="PowerPlusWaterMarkObject1" type="#_x0000_t136" '
                    'style="rotation:315;position:absolute">'
                    f'<v:textpath string="{watermark_text}"/>'
                    '</v:shape></w:pict></w:r></w:p>'
                    '</w:hdr>'
                ),
            )
            package.writestr(
                "word/_rels/document.xml.rels",
                '<?xml version="1.0"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" '
                'Target="header1.xml"/>'
                "</Relationships>",
            )
    return output.getvalue()


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_upload_and_delete_pdf(client: TestClient) -> None:
    source = b"%PDF-1.7\n%%EOF"
    response = client.post(
        "/api/v1/assets",
        files={"file": ("resume.pdf", source, "application/pdf")},
    )
    assert response.status_code == 201
    asset = response.json()
    assert asset["kind"] == "pdf"
    assert asset["display_name"] == "resume.pdf"
    assert len(asset["sha256"]) == 64

    lookup = client.get(f"/api/v1/assets/{asset['id']}")
    assert lookup.status_code == 200
    assert lookup.json()["sha256"] == asset["sha256"]

    content = client.get(f"/api/v1/assets/{asset['id']}/content")
    assert content.status_code == 200
    assert content.content == source
    assert content.headers["content-disposition"].startswith("inline;")

    deleted = client.delete(f"/api/v1/assets/{asset['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/assets/{asset['id']}").status_code == 404


def test_rejects_unknown_file_type(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assets",
        files={"file": ("payload.txt", b"not a supported file", "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        "/api/v1/assets",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE"


def test_inspects_docx_vml_watermark_candidate(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={
            "file": (
                "draft.docx",
                make_docx("DRAFT"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert uploaded.status_code == 201

    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"], "watermark_text": "DRAFT"},
    )
    assert scanned.status_code == 201
    analysis = scanned.json()
    assert analysis["status"] == "complete"
    assert analysis["inspected_parts"] == ["word/header1.xml"]
    assert len(analysis["candidates"]) == 1
    candidate = analysis["candidates"][0]
    assert candidate["content"] == "DRAFT"
    assert candidate["classification"] == "confirmed"
    assert candidate["source_locator"]["shape_type"] == "#_x0000_t136"

    lookup = client.get(f"/api/v1/analyses/{analysis['id']}")
    assert lookup.status_code == 200
    assert lookup.json() == analysis


def test_docx_candidate_is_ambiguous_without_user_target(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("draft.docx", make_docx("DRAFT"))},
    )
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    )
    assert scanned.status_code == 201
    assert scanned.json()["candidates"][0]["classification"] == "ambiguous"


def test_docx_rejects_codecv_preset(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("draft.docx", make_docx("DRAFT"))}
    )
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"], "preset": "codecv"},
    )
    assert scanned.status_code == 409
    assert scanned.json()["error"]["code"] == "ANALYSIS_NOT_AVAILABLE"


def test_docx_without_header_has_no_candidates(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("clean.docx", make_docx())},
    )
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    )
    assert scanned.status_code == 201
    assert scanned.json()["candidates"] == []


def test_pdf_analysis_requires_preset(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("paper.pdf", b"%PDF-1.7\n%%EOF")},
    )
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    )
    assert scanned.status_code == 409
    assert scanned.json()["error"]["code"] == "ANALYSIS_NOT_AVAILABLE"


def test_rejects_invalid_docx_container_during_analysis(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("broken.docx", b"PK\x03\x04not-really-a-zip")},
    )
    assert uploaded.status_code == 201
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "INVALID_DOCX"


def test_rejects_docx_with_unsafe_internal_path(client: TestClient) -> None:
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as package:
        package.writestr("../escape.xml", "bad")
        package.writestr("[Content_Types].xml", "<Types/>")
        package.writestr("word/document.xml", "<document/>")
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("unsafe.docx", output.getvalue())},
    )
    scanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "INVALID_DOCX"


def test_deleting_asset_removes_saved_analysis(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("draft.docx", make_docx("DRAFT"))},
    )
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"]},
    ).json()
    assert client.delete(f"/api/v1/assets/{uploaded.json()['id']}").status_code == 204
    response = client.get(f"/api/v1/analyses/{analysis['id']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"


def test_validates_plan_and_generates_clean_docx_copy(client: TestClient) -> None:
    source_bytes = make_docx("DRAFT")
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("draft.docx", source_bytes)}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "watermark_text": "DRAFT"},
    ).json()
    candidate_id = analysis["candidates"][0]["candidate_id"]

    planned = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": uploaded["id"],
            "asset_sha256": uploaded["sha256"],
            "analysis_id": analysis["id"],
            "operations": [{"candidate_id": candidate_id, "strategy": "object"}],
        },
    )
    assert planned.status_code == 200
    assert planned.json()["valid"] is True
    assert planned.json()["id"]

    created = client.post(
        "/api/v1/tasks", json={"plan_id": planned.json()["id"]}
    )
    assert created.status_code == 202
    task = created.json()
    deadline = monotonic() + 10
    while task["status"] in {"queued", "running"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task["status"] == "succeeded", task
    assert len(task["artifacts"]) == 1
    assert task["artifacts"][0]["role"] == "output"
    assert task["comparison"] == {
        "available": False,
        "removed_count": 1,
        "changed_parts": ["word/header1.xml"],
        "source_page_count": 0,
        "result_page_count": 0,
        "pages": [],
        "warning": "未能生成页面预览；无水印 DOCX 仍可正常下载。",
    }

    artifact = task["artifacts"][0]
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    with ZipFile(BytesIO(source_bytes)) as source, ZipFile(BytesIO(downloaded.content)) as output:
        assert output.read("word/document.xml") == source.read("word/document.xml")
        assert b"DRAFT" in source.read("word/header1.xml")
        assert b"DRAFT" not in output.read("word/header1.xml")


def test_ambiguous_candidate_requires_explicit_acknowledgement(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("draft.docx", make_docx("DRAFT"))}
    ).json()
    analysis = client.post(
        "/api/v1/analyses", json={"asset_id": uploaded["id"]}
    ).json()
    candidate_id = analysis["candidates"][0]["candidate_id"]
    payload = {
        "asset_id": uploaded["id"],
        "asset_sha256": uploaded["sha256"],
        "analysis_id": analysis["id"],
        "operations": [{"candidate_id": candidate_id, "strategy": "object"}],
    }

    unconfirmed = client.post("/api/v1/plans/validate", json=payload)
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["valid"] is False
    assert unconfirmed.json()["id"] is None
    warning_code = unconfirmed.json()["warnings"][0]["code"]

    payload["acknowledged_warnings"] = [warning_code]
    confirmed = client.post("/api/v1/plans/validate", json=payload)
    assert confirmed.status_code == 200
    assert confirmed.json()["valid"] is True
    assert confirmed.json()["id"]


def test_rejects_plan_with_unknown_candidate(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("draft.docx", make_docx("DRAFT"))}
    ).json()
    analysis = client.post(
        "/api/v1/analyses", json={"asset_id": uploaded["id"]}
    ).json()
    response = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": uploaded["id"],
            "asset_sha256": uploaded["sha256"],
            "analysis_id": analysis["id"],
            "operations": [{"candidate_id": "missing", "strategy": "object"}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PLAN"
