from io import BytesIO
from time import monotonic, sleep

from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
)


def make_pdf(
    *,
    codecv_signature: bool = True,
    include_pattern_resource: bool = True,
    encrypted: bool = False,
) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    body_text = b"BT /F1 12 Tf 72 720 Td (Resume body) Tj ET\n"

    if codecv_signature:
        pattern = DecodedStreamObject()
        pattern.set_data(b"0.92 g 0 0 30 30 re f\n")
        pattern.update(
            {
                NameObject("/Type"): NameObject("/Pattern"),
                NameObject("/PatternType"): NumberObject(1),
                NameObject("/PaintType"): NumberObject(1),
                NameObject("/TilingType"): NumberObject(1),
                NameObject("/BBox"): ArrayObject(
                    [FloatObject(0), FloatObject(0), FloatObject(30), FloatObject(30)]
                ),
                NameObject("/XStep"): FloatObject(30),
                NameObject("/YStep"): FloatObject(30),
                NameObject("/Resources"): DictionaryObject(),
            }
        )
        if include_pattern_resource:
            pattern_ref = writer._add_object(pattern)
            resources[NameObject("/Pattern")] = DictionaryObject(
                {NameObject("/Watermark1"): pattern_ref}
            )
        content_data = body_text + (
            b"/Pattern CS /Pattern cs /Watermark1 SCN /Watermark1 scn "
            b"0 0 612 792 re f\n"
        )
    else:
        content_data = body_text + b"0.9 g 10 10 100 100 re f\n"

    content = DecodedStreamObject()
    content.set_data(content_data)
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(content)
    if encrypted:
        writer.encrypt("secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload_pdf(client: TestClient, data: bytes) -> dict:
    response = client.post(
        "/api/v1/assets",
        files={"file": ("resume.pdf", data, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_codecv_inspector_matches_operation_signature(client: TestClient) -> None:
    asset = upload_pdf(client, make_pdf())

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    )

    assert response.status_code == 201
    analysis = response.json()
    assert analysis["preset"] == "codecv"
    assert analysis["match_status"] == "matched"
    assert analysis["inspected_parts"] == ["page:1"]
    assert len(analysis["candidates"]) == 1
    candidate = analysis["candidates"][0]
    assert candidate["classification"] == "confirmed"
    assert candidate["kind"] == "pattern"
    assert candidate["allowed_strategies"] == ["object"]
    assert candidate["source_locator"]["page_numbers"] == [1]
    assert candidate["source_locator"]["resource_name"] == "/Watermark1"
    assert candidate["source_locator"]["object_number"] is not None
    assert candidate["source_locator"]["operation_index"] is not None
    assert '"PatternType":1.0' in candidate["style"]


def test_codecv_inspector_does_not_match_ordinary_page_fill(client: TestClient) -> None:
    asset = upload_pdf(client, make_pdf(codecv_signature=False))

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    )

    assert response.status_code == 201
    assert response.json()["match_status"] == "not_found"
    assert response.json()["candidates"] == []


def test_codecv_inspector_marks_unresolved_pattern_for_review(client: TestClient) -> None:
    asset = upload_pdf(client, make_pdf(include_pattern_resource=False))

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    )

    assert response.status_code == 201
    assert response.json()["match_status"] == "needs_review"
    assert response.json()["candidates"][0]["classification"] == "ambiguous"


def test_pdf_analysis_requires_explicit_codecv_preset(client: TestClient) -> None:
    asset = upload_pdf(client, make_pdf())

    response = client.post("/api/v1/analyses", json={"asset_id": asset["id"]})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ANALYSIS_NOT_AVAILABLE"


def test_codecv_inspector_rejects_encrypted_pdf(client: TestClient) -> None:
    asset = upload_pdf(client, make_pdf(encrypted=True))

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PASSWORD_REQUIRED"


def test_codecv_inspector_rejects_truncated_pdf(client: TestClient) -> None:
    asset = upload_pdf(client, b"%PDF-1.7\ntruncated")

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PDF"


def test_codecv_plan_generates_valid_clean_pdf_copy(client: TestClient) -> None:
    source_bytes = make_pdf()
    asset = upload_pdf(client, source_bytes)
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "codecv"},
    ).json()
    candidate_id = analysis["candidates"][0]["candidate_id"]

    planned = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": asset["id"],
            "asset_sha256": asset["sha256"],
            "analysis_id": analysis["id"],
            "operations": [{"candidate_id": candidate_id, "strategy": "object"}],
        },
    )
    assert planned.status_code == 200
    assert planned.json()["valid"] is True
    assert planned.json()["output_kind"] == "pdf"

    created = client.post("/api/v1/tasks", json={"plan_id": planned.json()["id"]})
    assert created.status_code == 202
    task = created.json()
    deadline = monotonic() + 10
    while task["status"] in {"queued", "running"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()

    assert task["status"] == "succeeded", task
    assert task["comparison"]["removed_count"] == 1
    assert task["comparison"]["changed_parts"] == ["page:1"]
    artifact = next(item for item in task["artifacts"] if item["role"] == "output")
    assert artifact["media_type"] == "application/pdf"
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    assert "cleaned.pdf" in downloaded.headers["content-disposition"]
    result = PdfReader(BytesIO(downloaded.content))
    assert len(result.pages) == 1
    assert result.pages[0].extract_text().strip() == "Resume body"

    clean_asset = upload_pdf(client, downloaded.content)
    rescanned = client.post(
        "/api/v1/analyses",
        json={"asset_id": clean_asset["id"], "preset": "codecv"},
    )
    assert rescanned.status_code == 201
    assert rescanned.json()["match_status"] == "not_found"
