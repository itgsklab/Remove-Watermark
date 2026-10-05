from io import BytesIO
from time import monotonic, sleep

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from wmrm.adapters.images.metadata import ImageInspector
from wmrm.application.assets import AssetError
from wmrm.benchmarks.image_quality import generate_cases


def make_image(
    image_format: str,
    *,
    size: tuple[int, int] = (100, 50),
    orientation: int = 1,
) -> bytes:
    output = BytesIO()
    image = Image.new("RGBA" if image_format == "PNG" else "RGB", size, "#d2b48c")
    arguments = {}
    if image_format == "JPEG" and orientation != 1:
        exif = Image.Exif()
        exif[274] = orientation
        arguments["exif"] = exif
    image.save(output, format=image_format, **arguments)
    return output.getvalue()


def make_animated_webp() -> bytes:
    output = BytesIO()
    first = Image.new("RGB", (32, 24), "#d2b48c")
    second = Image.new("RGB", (32, 24), "#806040")
    first.save(
        output,
        format="WEBP",
        save_all=True,
        append_images=[second],
        duration=100,
        loop=0,
        lossless=True,
    )
    return output.getvalue()


def make_watermarked_png() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (80, 60), "#d2b48c")
    ImageDraw.Draw(image).rectangle((25, 20, 54, 34), fill="#332211")
    image.save(output, format="PNG")
    return output.getvalue()


def make_benchmark_png(case_id: str) -> bytes:
    case = next(item for item in generate_cases() if item.case_id == case_id)
    output = BytesIO()
    Image.fromarray(case.watermarked).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    ("filename", "image_format", "kind"),
    [
        ("sample.png", "PNG", "png"),
        ("sample.jpg", "JPEG", "jpeg"),
        ("sample.webp", "WEBP", "webp"),
    ],
)
def test_image_analysis_reports_safe_metadata(
    client: TestClient, filename: str, image_format: str, kind: str
) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": (filename, make_image(image_format))},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["kind"] == kind

    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded.json()["id"], "preset": "image"},
    )
    assert response.status_code == 201
    analysis = response.json()
    metadata = analysis["image_metadata"]
    assert analysis["preset"] == "image"
    assert analysis["candidates"] == []
    assert metadata["format"] == image_format
    assert metadata["width"] == 100
    assert metadata["height"] == 50
    assert metadata["display_width"] == 100
    assert metadata["display_height"] == 50
    assert metadata["frames"] == 1
    assert metadata["animated"] is False
    assert metadata["transform_id"]


def test_image_analysis_applies_exif_orientation_to_display_geometry(
    client: TestClient,
) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("rotated.jpg", make_image("JPEG", size=(40, 20), orientation=6))},
    ).json()

    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()

    metadata = analysis["image_metadata"]
    assert metadata["width"] == 40
    assert metadata["height"] == 20
    assert metadata["display_width"] == 20
    assert metadata["display_height"] == 40
    assert metadata["exif_orientation"] == 6
    assert "image:exif-orientation" in analysis["inspected_parts"]


def test_image_mask_preview_validates_bounds_and_union_area(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("mask.png", make_image("PNG"))},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    transform_id = analysis["image_metadata"]["transform_id"]

    response = client.post(
        "/api/v1/image-masks/preview",
        json={
            "asset_id": uploaded["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {"x0": 0, "y0": 0, "x1": 20, "y1": 20, "transform_id": transform_id},
                {
                    "x0": 10,
                    "y0": 10,
                    "x1": 30,
                    "y1": 30,
                    "transform_id": transform_id,
                },
            ],
        },
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["valid"] is True
    assert preview["executable"] is True
    assert preview["covered_pixels"] == 700
    assert preview["coverage_ratio"] == pytest.approx(0.14)
    assert preview["requires_acknowledgement"] is True
    assert preview["selection_risk"]["large_selection"] is True
    assert preview["selection_risk"]["level"] == "review"

    invalid = client.post(
        "/api/v1/image-masks/preview",
        json={
            "asset_id": uploaded["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {"x0": 0, "y0": 0, "x1": 101, "y1": 20, "transform_id": transform_id}
            ],
        },
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "PLAN_STALE"


def test_image_mask_preview_counts_rasterized_fractional_pixels(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("fractional.png", make_image("PNG"))}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    response = client.post(
        "/api/v1/image-masks/preview",
        json={
            "asset_id": uploaded["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "x0": 0.2,
                    "y0": 0.2,
                    "x1": 1.1,
                    "y1": 1.1,
                    "transform_id": analysis["image_metadata"]["transform_id"],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["covered_pixels"] == 4


def test_image_analysis_rejects_corrupt_payload(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("broken.png", b"\x89PNG\r\n\x1a\nnot-an-image")},
    ).json()
    response = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_IMAGE"


def test_animated_image_is_inspected_but_mask_requires_review(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("animated.webp", make_animated_webp())},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    metadata = analysis["image_metadata"]
    assert metadata["animated"] is True
    assert metadata["frames"] == 2
    assert "image:animation" in analysis["inspected_parts"]

    preview = client.post(
        "/api/v1/image-masks/preview",
        json={
            "asset_id": uploaded["id"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "x0": 0,
                    "y0": 0,
                    "x1": 10,
                    "y1": 10,
                    "transform_id": metadata["transform_id"],
                }
            ],
        },
    ).json()
    assert preview["requires_acknowledgement"] is True
    assert any("逐帧蒙版" in warning for warning in preview["warnings"])


def test_image_inspector_enforces_pixel_limits(tmp_path) -> None:
    path = tmp_path / "large.png"
    path.write_bytes(make_image("PNG", size=(20, 20)))
    inspector = ImageInspector(max_dimension=100, max_pixels=399, max_frames=10)

    with pytest.raises(AssetError) as captured:
        inspector.inspect(path, "0" * 64, "png")

    assert captured.value.code == "RESOURCE_LIMIT"


def test_image_plan_runs_opencv_and_preserves_pixels_outside_mask(
    client: TestClient,
) -> None:
    source_bytes = make_watermarked_png()
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("watermark.png", source_bytes)}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    region = {
        "x0": 25,
        "y0": 20,
        "x1": 55,
        "y1": 35,
        "transform_id": analysis["image_metadata"]["transform_id"],
    }
    planned = client.post(
        "/api/v1/image-plans/validate",
        json={
            "asset_id": uploaded["id"],
            "asset_sha256": uploaded["sha256"],
            "analysis_id": analysis["id"],
            "regions": [region],
            "radius": 3,
        },
    )
    assert planned.status_code == 200
    assert planned.json()["valid"] is True
    assert planned.json()["output_kind"] == "png"

    created = client.post("/api/v1/tasks", json={"plan_id": planned.json()["id"]})
    assert created.status_code == 202
    task = created.json()
    deadline = monotonic() + 15
    while task["status"] in {"queued", "running"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()

    assert task["status"] == "succeeded", task
    assert "1 个蒙版区域" in task["stage"]
    assert task["comparison"] is None
    assert len(task["artifacts"]) == 1
    artifact = task["artifacts"][0]
    assert artifact["role"] == "output"
    assert artifact["media_type"] == "image/png"
    downloaded = client.get(artifact["download_url"])
    assert downloaded.status_code == 200
    assert "cleaned.png" in downloaded.headers["content-disposition"]

    source = np.asarray(Image.open(BytesIO(source_bytes)).convert("RGB"))
    result = np.asarray(Image.open(BytesIO(downloaded.content)).convert("RGB"))
    mask = np.zeros(source.shape[:2], dtype=bool)
    mask[20:35, 25:55] = True
    assert result.shape == source.shape
    assert np.array_equal(result[~mask], source[~mask])
    assert np.any(result[mask] != source[mask])


def test_large_image_plan_requires_explicit_acknowledgement(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("large-mask.png", make_image("PNG"))}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    payload = {
        "asset_id": uploaded["id"],
        "asset_sha256": uploaded["sha256"],
        "analysis_id": analysis["id"],
        "regions": [
            {
                "x0": 0,
                "y0": 0,
                "x1": 60,
                "y1": 50,
                "transform_id": analysis["image_metadata"]["transform_id"],
            }
        ],
    }

    unconfirmed = client.post("/api/v1/image-plans/validate", json=payload)
    assert unconfirmed.status_code == 200
    assert unconfirmed.json()["valid"] is False
    assert unconfirmed.json()["id"] is None

    payload["acknowledged_warnings"] = [
        "IMAGE_MASK_OVER_25_PERCENT",
        "IMAGE_LOW_CONTRAST_SELECTION",
    ]
    confirmed = client.post("/api/v1/image-plans/validate", json=payload)
    assert confirmed.status_code == 200
    assert confirmed.json()["valid"] is True
    assert confirmed.json()["id"]


def test_low_contrast_image_plan_requires_explicit_acknowledgement(
    client: TestClient,
) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("faint.png", make_image("PNG"))}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    payload = {
        "asset_id": uploaded["id"],
        "asset_sha256": uploaded["sha256"],
        "analysis_id": analysis["id"],
        "regions": [
            {
                "x0": 40,
                "y0": 20,
                "x1": 50,
                "y1": 30,
                "transform_id": analysis["image_metadata"]["transform_id"],
            }
        ],
    }

    preview = client.post("/api/v1/image-masks/preview", json=payload).json()
    assert preview["coverage_ratio"] == pytest.approx(0.02)
    assert preview["selection_risk"]["large_selection"] is False
    assert preview["selection_risk"]["regions"][0]["low_contrast"] is True
    assert preview["requires_acknowledgement"] is True

    unconfirmed = client.post("/api/v1/image-plans/validate", json=payload).json()
    assert unconfirmed["valid"] is False
    assert any(
        warning["code"] == "IMAGE_LOW_CONTRAST_SELECTION"
        for warning in unconfirmed["warnings"]
    )

    payload["acknowledged_warnings"] = ["IMAGE_LOW_CONTRAST_SELECTION"]
    confirmed = client.post("/api/v1/image-plans/validate", json=payload).json()
    assert confirmed["valid"] is True
    assert confirmed["id"]


def test_complex_image_plan_requires_explicit_acknowledgement(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("stripes.png", make_benchmark_png("stripes"))},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    payload = {
        "asset_id": uploaded["id"],
        "asset_sha256": uploaded["sha256"],
        "analysis_id": analysis["id"],
        "regions": [
            {
                "x0": 82,
                "y0": 56,
                "x1": 174,
                "y1": 104,
                "transform_id": analysis["image_metadata"]["transform_id"],
            }
        ],
    }

    preview = client.post("/api/v1/image-masks/preview", json=payload).json()
    assert preview["complexity"]["level"] == "high"
    assert preview["requires_acknowledgement"] is True

    unconfirmed = client.post("/api/v1/image-plans/validate", json=payload).json()
    assert unconfirmed["valid"] is False
    assert any(
        warning["code"] == "IMAGE_COMPLEXITY_HIGH"
        for warning in unconfirmed["warnings"]
    )
    assert any(
        warning["code"] == "IMAGE_MASK_OVER_10_PERCENT"
        for warning in unconfirmed["warnings"]
    )

    payload["acknowledged_warnings"] = [
        "IMAGE_COMPLEXITY_HIGH",
        "IMAGE_MASK_OVER_10_PERCENT",
    ]
    confirmed = client.post("/api/v1/image-plans/validate", json=payload).json()
    assert confirmed["valid"] is True
    assert confirmed["id"]


def test_animated_image_cannot_create_inpaint_plan(client: TestClient) -> None:
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("animated.webp", make_animated_webp())}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "preset": "image"},
    ).json()
    response = client.post(
        "/api/v1/image-plans/validate",
        json={
            "asset_id": uploaded["id"],
            "asset_sha256": uploaded["sha256"],
            "analysis_id": analysis["id"],
            "regions": [
                {
                    "x0": 0,
                    "y0": 0,
                    "x1": 10,
                    "y1": 10,
                    "transform_id": analysis["image_metadata"]["transform_id"],
                }
            ],
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMAGE_PLAN_NOT_AVAILABLE"
