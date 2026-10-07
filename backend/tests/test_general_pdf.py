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
    TextStringObject,
)
from test_codecv_pdf import make_pdf as make_pattern_pdf

from wmrm.benchmarks.pdf_redaction_probe import _fixture_pdf


def make_general_pdf(
    *, pages: int = 2, repeated_text: str = "DRAFT", crop_origin: bool = False
) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    image = DecodedStreamObject()
    image.set_data(b"\xc8\xc8\xc8")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)

    for page_index in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        if crop_origin:
            page.cropbox.lower_left = (10, 20)
            page.cropbox.upper_right = (602, 772)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
                NameObject("/XObject"): DictionaryObject(
                    {NameObject("/ImWatermark"): image_ref}
                ),
            }
        )
        content = DecodedStreamObject()
        page_text = repeated_text if pages > 1 else "Body paragraph"
        content.set_data(
            (
                "q 80 0 0 40 250 350 cm /ImWatermark Do Q "
                f"BT /F1 24 Tf 200 500 Td ({page_text}) Tj ET\n"
            ).encode()
        )
        page[NameObject("/Contents")] = writer._add_object(content)
        if page_index == 0 and pages > 1:
            annotation = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Watermark"),
                    NameObject("/Rect"): ArrayObject(
                        [
                            FloatObject(100),
                            FloatObject(100),
                            FloatObject(300),
                            FloatObject(160),
                        ]
                    ),
                    NameObject("/Contents"): TextStringObject("Review watermark"),
                }
            )
            link = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Annot"),
                    NameObject("/Subtype"): NameObject("/Link"),
                    NameObject("/Rect"): ArrayObject(
                        [
                            FloatObject(400),
                            FloatObject(100),
                            FloatObject(500),
                            FloatObject(130),
                        ]
                    ),
                }
            )
            page[NameObject("/Annots")] = ArrayObject(
                [writer._add_object(annotation), writer._add_object(link)]
            )

    if pages > 1:
        ocg = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/OCG"),
                NameObject("/Name"): TextStringObject("DRAFT watermark layer"),
            }
        )
        writer._root_object[NameObject("/OCProperties")] = DictionaryObject(
            {NameObject("/OCGs"): ArrayObject([writer._add_object(ocg)])}
        )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def make_nested_form_pdf() -> bytes:
    writer = PdfWriter()
    image = DecodedStreamObject()
    image.set_data(b"\x80\x80\x80")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)
    form = DecodedStreamObject()
    form.set_data(b"q 20 0 0 10 10 15 cm /ImInner Do Q")
    form.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/FormType"): NumberObject(1),
            NameObject("/BBox"): ArrayObject(
                [FloatObject(0), FloatObject(0), FloatObject(100), FloatObject(50)]
            ),
            NameObject("/Matrix"): ArrayObject(
                [
                    FloatObject(1),
                    FloatObject(0),
                    FloatObject(0),
                    FloatObject(1),
                    FloatObject(5),
                    FloatObject(7),
                ]
            ),
            NameObject("/Resources"): DictionaryObject(
                {
                    NameObject("/XObject"): DictionaryObject(
                        {NameObject("/ImInner"): image_ref}
                    )
                }
            ),
        }
    )
    form_ref = writer._add_object(form)
    page = writer.add_blank_page(width=612, height=792)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/XObject"): DictionaryObject(
                {NameObject("/FmOuter"): form_ref}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"q 2 0 0 2 100 200 cm /FmOuter Do Q")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client: TestClient, payload: bytes) -> dict:
    response = client.post(
        "/api/v1/assets",
        files={"file": ("general.pdf", payload, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


def test_general_pdf_inventory_classifies_review_candidates(client: TestClient) -> None:
    asset = upload(client, make_general_pdf())

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    )

    assert response.status_code == 201
    analysis = response.json()
    assert analysis["preset"] == "general"
    assert analysis["match_status"] == "needs_review"
    assert analysis["inspected_parts"] == [
        "page:1",
        "page:2",
        "catalog:optional-content",
    ]
    assert len(analysis["pdf_pages"]) == 2
    assert analysis["pdf_pages"][0]["transform_id"]
    protected_kinds = {item["kind"] for item in analysis["protected_content"]}
    assert {"text", "image", "annotation", "link"} <= protected_kinds
    text = [item for item in analysis["candidates"] if item["kind"] == "text"]
    images = [item for item in analysis["candidates"] if item["kind"] == "image"]
    annotation = next(
        item for item in analysis["candidates"] if "annotation" in item["evidence"]
    )
    ocg = next(
        item for item in analysis["candidates"] if item["content"] == "DRAFT watermark layer"
    )
    assert len(text) == 2
    assert all(item["classification"] == "ambiguous" for item in text)
    assert all(item["region"]["approximate"] is True for item in text)
    assert len(images) == 2
    assert all(item["classification"] == "ambiguous" for item in images)
    assert images[0]["source_locator"]["resource_name"] == "/ImWatermark"
    assert images[0]["region"]["x0"] == 250
    assert images[0]["region"]["y0"] == 350
    assert images[0]["region"]["transform_id"] == analysis["pdf_pages"][0][
        "transform_id"
    ]
    assert annotation["classification"] == "confirmed"
    assert annotation["source_locator"]["annotation_index"] == 0
    assert ocg["classification"] == "ambiguous"
    assert all(item["allowed_strategies"] == [] for item in analysis["candidates"])


def test_general_pdf_target_text_is_candidate_on_single_page(client: TestClient) -> None:
    asset = upload(client, make_general_pdf(pages=1))

    response = client.post(
        "/api/v1/analyses",
        json={
            "asset_id": asset["id"],
            "preset": "general",
            "watermark_text": "Body paragraph",
        },
    )

    assert response.status_code == 201
    text = [item for item in response.json()["candidates"] if item["kind"] == "text"]
    assert len(text) == 1
    assert text[0]["classification"] == "ambiguous"
    assert text[0]["overlaps_protected_content"] is True


def test_general_pdf_without_reviewable_evidence_reports_not_found(
    client: TestClient,
) -> None:
    asset = upload(client, make_general_pdf(pages=1))

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    )

    assert response.status_code == 201
    assert response.json()["match_status"] == "not_found"
    assert [item["classification"] for item in response.json()["candidates"]] == [
        "content"
    ]


def test_general_pdf_candidates_cannot_create_destructive_plan(client: TestClient) -> None:
    asset = upload(client, make_general_pdf())
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()

    response = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": asset["id"],
            "asset_sha256": asset["sha256"],
            "analysis_id": analysis["id"],
            "operations": [
                {
                    "candidate_id": analysis["candidates"][0]["candidate_id"],
                    "strategy": "object",
                }
            ],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAN_NOT_AVAILABLE"


def test_general_pdf_inventory_lists_pattern_use(client: TestClient) -> None:
    asset = upload(client, make_pattern_pdf())

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    )

    assert response.status_code == 201
    pattern = next(
        item for item in response.json()["candidates"] if item["kind"] == "pattern"
    )
    assert pattern["classification"] == "ambiguous"
    assert pattern["source_locator"]["resource_name"] == "/Watermark1"
    assert pattern["source_locator"]["operation_index"] is not None
    assert "graphic" in {
        item["kind"] for item in response.json()["protected_content"]
    }


def test_redaction_preview_reports_protected_content_overlap(client: TestClient) -> None:
    asset = upload(client, make_general_pdf())
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()
    page = analysis["pdf_pages"][0]

    response = client.post(
        "/api/v1/redactions/preview",
        json={
            "asset_id": asset["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "page_number": 1,
                    "x0": 250,
                    "y0": 350,
                    "x1": 330,
                    "y1": 390,
                    "transform_id": page["transform_id"],
                }
            ],
        },
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["valid"] is True
    assert preview["executable"] is True
    assert preview["requires_acknowledgement"] is True
    assert [item["kind"] for item in preview["regions"][0]["overlaps"]] == [
        "image"
    ]
    assert preview["regions"][0]["overlaps"][0]["intersection_area"] == 3200


def test_general_pdf_redaction_plan_executes_in_worker(client: TestClient) -> None:
    asset = upload(client, make_general_pdf(pages=1))
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()
    region = {
        "page_number": 1,
        "x0": 190,
        "y0": 490,
        "x1": 380,
        "y1": 535,
        "transform_id": analysis["pdf_pages"][0]["transform_id"],
    }
    payload = {
        "asset_id": asset["id"],
        "asset_sha256": asset["sha256"],
        "analysis_id": analysis["id"],
        "regions": [region],
        "acknowledged_warnings": [],
    }

    review = client.post("/api/v1/redaction-plans/validate", json=payload)
    assert review.status_code == 200
    assert review.json()["valid"] is False
    assert review.json()["warnings"][1]["code"] == "PDF_REDACTION_OVERLAP"

    payload["acknowledged_warnings"] = ["PDF_REDACTION_OVERLAP"]
    plan = client.post("/api/v1/redaction-plans/validate", json=payload)
    assert plan.status_code == 200
    assert plan.json()["valid"] is True
    assert plan.json()["license_mode"] == "agpl"

    created = client.post("/api/v1/tasks", json={"plan_id": plan.json()["id"]})
    assert created.status_code == 202
    deadline = monotonic() + 10
    task = created.json()
    while task["status"] not in {"succeeded", "failed"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task["status"] == "succeeded", task.get("error")
    assert "物理删除 1 个 PDF 区域" in task["stage"]
    assert task["comparison"]["removed_count"] == 1
    assert task["comparison"]["changed_parts"] == ["page:1"]

    artifact = next(item for item in task["artifacts"] if item["role"] == "output")
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    result = PdfReader(BytesIO(downloaded.content), strict=True)
    assert "Body paragraph" not in (result.pages[0].extract_text() or "")


def test_general_pdf_raster_inpaint_reinjects_searchable_text(client: TestClient) -> None:
    asset = upload(client, _fixture_pdf())
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()
    region = {
        "page_number": 1,
        "x0": 80,
        "y0": 660,
        "x1": 235,
        "y1": 715,
        "transform_id": analysis["pdf_pages"][0]["transform_id"],
    }
    payload = {
        "asset_id": asset["id"],
        "asset_sha256": asset["sha256"],
        "analysis_id": analysis["id"],
        "regions": [region],
        "strategy": "raster_inpaint",
        "dpi": 96,
        "radius": 3,
        "ocr_languages": "eng",
        "acknowledged_warnings": ["PDF_REDACTION_OVERLAP", "PDF_RASTERIZATION"],
    }

    plan = client.post("/api/v1/redaction-plans/validate", json=payload)
    assert plan.status_code == 200
    assert plan.json()["valid"] is True
    assert plan.json()["strategy"] == "raster_inpaint"
    assert plan.json()["dpi"] == 96

    created = client.post("/api/v1/tasks", json={"plan_id": plan.json()["id"]})
    assert created.status_code == 202
    deadline = monotonic() + 10
    task = created.json()
    while task["status"] not in {"succeeded", "failed"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task["status"] == "succeeded", task.get("error")
    assert "栅格修复 1 个 PDF 区域并回灌文字层" in task["stage"]

    artifact = next(item for item in task["artifacts"] if item["role"] == "output")
    downloaded = client.get(artifact["download_url"])
    result = PdfReader(BytesIO(downloaded.content), strict=True)
    text = result.pages[0].extract_text() or ""
    assert "REMOVE-ME" not in text
    assert "KEEP-ME" in text


def test_redaction_preview_rejects_stale_page_transform(client: TestClient) -> None:
    asset = upload(client, make_general_pdf())
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()

    response = client.post(
        "/api/v1/redactions/preview",
        json={
            "asset_id": asset["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "page_number": 1,
                    "x0": 1,
                    "y0": 1,
                    "x1": 10,
                    "y1": 10,
                    "transform_id": "stale-transform",
                }
            ],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PLAN_STALE"


def test_general_pdf_regions_are_relative_to_crop_box_origin(client: TestClient) -> None:
    asset = upload(client, make_general_pdf(pages=1, crop_origin=True))

    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    ).json()

    page = analysis["pdf_pages"][0]
    image = next(item for item in analysis["protected_content"] if item["kind"] == "image")
    assert page["crop_x"] == 10
    assert page["crop_y"] == 20
    assert page["width"] == 592
    assert page["height"] == 752
    assert image["region"]["x0"] == 240
    assert image["region"]["y0"] == 330
    assert image["region"]["transform_id"] == page["transform_id"]


def test_general_pdf_recurses_into_form_xobjects(client: TestClient) -> None:
    asset = upload(client, make_nested_form_pdf())

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": asset["id"], "preset": "general"},
    )

    assert response.status_code == 201
    analysis = response.json()
    form = next(
        item for item in analysis["protected_content"] if item["kind"] == "form"
    )
    image = next(
        item for item in analysis["protected_content"] if item["kind"] == "image"
    )
    assert form["region"]["x0"] == 110
    assert form["region"]["y0"] == 214
    assert form["region"]["x1"] == 310
    assert form["region"]["y1"] == 314
    assert image["summary"] == "Image /FmOuter>/ImInner"
    assert image["region"]["x0"] == 130
    assert image["region"]["y0"] == 244
    assert image["region"]["x1"] == 170
    assert image["region"]["y1"] == 264
    assert not any("尚未递归" in warning for warning in analysis["warnings"])

    preview = client.post(
        "/api/v1/redactions/preview",
        json={
            "asset_id": asset["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "page_number": 1,
                    "x0": 130,
                    "y0": 244,
                    "x1": 170,
                    "y1": 264,
                    "transform_id": analysis["pdf_pages"][0]["transform_id"],
                }
            ],
        },
    )
    assert preview.status_code == 200
    overlap_kinds = {
        item["kind"] for item in preview.json()["regions"][0]["overlaps"]
    }
    assert {"form", "image"} <= overlap_kinds
