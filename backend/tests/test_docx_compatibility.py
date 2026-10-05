import shutil
import subprocess
from io import BytesIO
from pathlib import Path
from time import monotonic, sleep
from zipfile import ZipFile

import pytest
from docx_compat import PROFILES, make_compatibility_docx
from fastapi.testclient import TestClient


@pytest.mark.parametrize("profile", PROFILES, ids=lambda profile: profile.id)
def test_supported_ooxml_profiles_complete_the_processing_flow(
    client: TestClient, profile
) -> None:
    source_bytes = make_compatibility_docx(profile, ("DRAFT",))
    uploaded = client.post(
        "/api/v1/assets",
        files={"file": (f"{profile.id}.docx", source_bytes)},
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "watermark_text": "draft"},
    ).json()
    assert analysis["inspected_parts"] == [profile.part_name]
    assert len(analysis["candidates"]) == 1
    candidate = analysis["candidates"][0]
    assert candidate["classification"] == "confirmed"
    assert candidate["source_locator"]["shape_index"] == int(profile.leading_shape)

    result_bytes = _process(client, uploaded, analysis, [candidate["candidate_id"]])
    with ZipFile(BytesIO(source_bytes)) as source, ZipFile(BytesIO(result_bytes)) as result:
        for name in source.namelist():
            if name != profile.part_name:
                assert result.read(name) == source.read(name)
        assert b"DRAFT" in source.read(profile.part_name)
        assert b"DRAFT" not in result.read(profile.part_name)


def test_selective_removal_preserves_other_vml_text_shape(client: TestClient) -> None:
    profile = PROFILES[0]
    source_bytes = make_compatibility_docx(profile, ("DRAFT", "CONFIDENTIAL"))
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("mixed-watermarks.docx", source_bytes)}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "watermark_text": "DRAFT"},
    ).json()
    selected = [
        item["candidate_id"]
        for item in analysis["candidates"]
        if item["classification"] == "confirmed"
    ]

    result_bytes = _process(client, uploaded, analysis, selected)
    with ZipFile(BytesIO(result_bytes)) as result:
        part = result.read(profile.part_name)
    assert b"DRAFT" not in part
    assert b"CONFIDENTIAL" in part


def test_removes_multiple_selected_shapes_from_same_part(client: TestClient) -> None:
    profile = PROFILES[1]
    source_bytes = make_compatibility_docx(profile, ("DRAFT", "DRAFT"))
    uploaded = client.post(
        "/api/v1/assets", files={"file": ("repeated-watermarks.docx", source_bytes)}
    ).json()
    analysis = client.post(
        "/api/v1/analyses",
        json={"asset_id": uploaded["id"], "watermark_text": "DRAFT"},
    ).json()
    selected = [item["candidate_id"] for item in analysis["candidates"]]
    assert len(selected) == 2

    result_bytes = _process(client, uploaded, analysis, selected)
    with ZipFile(BytesIO(result_bytes)) as result:
        part = result.read(profile.part_name)
    assert b"DRAFT" not in part
    assert b"DecorativeObject" in part


def test_scans_docx_generated_by_installed_libreoffice(
    client: TestClient, tmp_path: Path
) -> None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        pytest.skip("LibreOffice is not installed")
    html_path = tmp_path / "libreoffice-source.html"
    html_path.write_text("<html><body><h1>Compatibility</h1><p>Document body</p></body></html>")
    profile_path = tmp_path / "lo-profile"
    profile_path.mkdir()
    conversion = subprocess.run(
        [
            soffice,
            "--headless",
            "--nologo",
            f"-env:UserInstallation={profile_path.as_uri()}",
            "--convert-to",
            "docx:Office Open XML Text",
            "--outdir",
            str(tmp_path),
            str(html_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    docx_path = tmp_path / "libreoffice-source.docx"
    assert conversion.returncode == 0, conversion.stderr
    assert docx_path.is_file()

    uploaded = client.post(
        "/api/v1/assets",
        files={"file": ("libreoffice.docx", docx_path.read_bytes())},
    )
    assert uploaded.status_code == 201
    analysis = client.post(
        "/api/v1/analyses", json={"asset_id": uploaded.json()["id"]}
    )
    assert analysis.status_code == 201
    assert analysis.json()["candidates"] == []


def _process(
    client: TestClient,
    asset: dict,
    analysis: dict,
    candidate_ids: list[str],
) -> bytes:
    plan = client.post(
        "/api/v1/plans/validate",
        json={
            "asset_id": asset["id"],
            "asset_sha256": asset["sha256"],
            "analysis_id": analysis["id"],
            "operations": [
                {"candidate_id": candidate_id, "strategy": "object"}
                for candidate_id in candidate_ids
            ],
        },
    )
    assert plan.status_code == 200
    assert plan.json()["valid"] is True
    task = client.post("/api/v1/tasks", json={"plan_id": plan.json()["id"]}).json()
    deadline = monotonic() + 10
    while task["status"] in {"queued", "running"} and monotonic() < deadline:
        sleep(0.02)
        task = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert task["status"] == "succeeded", task
    output = next(item for item in task["artifacts"] if item["role"] == "output")
    response = client.get(output["download_url"])
    assert response.status_code == 200
    return response.content
