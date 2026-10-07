import io
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from test_api import make_docx
from test_codecv_pdf import make_pdf as make_codecv_pdf

import wmrm.cli as cli
from wmrm.adapters.pdf.raster_inpaint import PdfRasterInpaintError
from wmrm.benchmarks.pdf_redaction_probe import _fixture_pdf
from wmrm.cli import ExitCode, main


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(arguments, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def make_cli_image(path: Path, *, flat: bool = False) -> None:
    image = Image.new("RGB", (80, 60), "#d2b48c")
    if not flat:
        ImageDraw.Draw(image).rectangle((25, 20, 54, 34), fill="#332211")
    image.save(path, format="PNG")


def test_doctor_has_machine_readable_runtime_status() -> None:
    code, stdout, stderr = run_cli(["doctor", "--json"])

    payload = json.loads(stdout)
    assert code == ExitCode.SUCCESS
    assert stderr == ""
    assert payload["ok"] is True
    assert payload["command"] == "doctor"
    assert payload["result"]["pymupdf"]["available"] is True
    assert isinstance(payload["result"]["tesseract"]["available"], bool)


def test_usage_error_is_json_and_returns_two() -> None:
    code, stdout, stderr = run_cli(["--json", "pdf-deep"])

    payload = json.loads(stderr)
    assert code == ExitCode.USAGE
    assert stdout == ""
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_USAGE"


def test_pdf_deep_requires_explicit_acknowledgement_without_touching_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())
    output.write_bytes(b"existing")

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-deep",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--force",
        ]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.ACKNOWLEDGEMENT_REQUIRED
    assert stdout == ""
    assert payload["error"]["code"] == "RASTERIZATION_ACKNOWLEDGEMENT_REQUIRED"
    assert output.read_bytes() == b"existing"


def test_pdf_deep_generates_new_pdf_and_json_report(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-deep",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--dpi",
            "96",
            "--acknowledge-rasterization",
        ]
    )

    payload = json.loads(stdout)
    text = PdfReader(str(output), strict=True).pages[0].extract_text() or ""
    assert code == ExitCode.SUCCESS
    assert stderr == ""
    assert payload["result"]["rasterized_pages"] == [1]
    assert payload["result"]["output"] == str(output)
    assert "REMOVE-ME" not in text
    assert "KEEP-ME" in text


def test_pdf_redact_rejects_reversed_region_as_usage_error(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-redact",
            str(source),
            str(tmp_path / "result.pdf"),
            "--region",
            "1:20:20:10:10",
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
        ]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.USAGE
    assert stdout == ""
    assert payload["error"]["code"] == "INVALID_USAGE"


def test_pdf_deep_rejects_non_finite_region(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    source.write_bytes(_fixture_pdf())

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-deep",
            str(source),
            str(tmp_path / "result.pdf"),
            "--region",
            "1:0:0:nan:10",
            "--license-mode",
            "agpl",
            "--acknowledge-rasterization",
        ]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.USAGE
    assert stdout == ""
    assert payload["error"]["code"] == "INVALID_USAGE"


def test_pdf_redact_generates_new_pdf(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())

    code, stdout, stderr = run_cli(
        [
            "pdf-redact",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
            "--json",
        ]
    )

    payload = json.loads(stdout)
    text = PdfReader(str(output), strict=True).pages[0].extract_text() or ""
    assert code == ExitCode.SUCCESS
    assert stderr == ""
    assert payload["result"]["changed_pages"] == [1]
    assert "REMOVE-ME" not in text
    assert "KEEP-ME" in text


def test_cli_refuses_existing_output_without_force(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())
    output.write_bytes(b"existing")

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-redact",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
        ]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert payload["error"]["code"] == "OUTPUT_EXISTS"
    assert output.read_bytes() == b"existing"


def test_force_replaces_existing_output_only_after_success(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())
    output.write_bytes(b"existing")

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-redact",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--force",
            "--acknowledge-content-removal",
        ]
    )

    assert code == ExitCode.SUCCESS
    assert stderr == ""
    assert json.loads(stdout)["result"]["output"] == str(output)
    assert output.read_bytes() != b"existing"
    assert list(tmp_path.glob(".*.tmp.pdf")) == []


def test_force_preserves_existing_output_when_processing_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.pdf"
    output = tmp_path / "result.pdf"
    source.write_bytes(_fixture_pdf())
    output.write_bytes(b"existing")

    def fail(*args, **kwargs):
        raise PdfRasterInpaintError("probe failure")

    monkeypatch.setattr(cli, "raster_inpaint_pdf_regions", fail)
    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-deep",
            str(source),
            str(output),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--force",
            "--acknowledge-rasterization",
        ]
    )

    assert code == ExitCode.PROCESSING_FAILED
    assert stdout == ""
    assert json.loads(stderr)["error"]["code"] == "PROCESSING_FAILED"
    assert output.read_bytes() == b"existing"


def test_cli_refuses_to_overwrite_source(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    original = _fixture_pdf()
    source.write_bytes(original)

    code, stdout, stderr = run_cli(
        [
            "--json",
            "pdf-redact",
            str(source),
            str(source),
            "--region",
            "1:80:660:235:715",
            "--license-mode",
            "agpl",
            "--force",
            "--acknowledge-content-removal",
        ]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert payload["error"]["code"] == "OUTPUT_OVERWRITES_INPUT"
    assert source.read_bytes() == original


def test_image_plan_then_apply_generates_lossless_png(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    plan_path = tmp_path / "plan.json"
    output = tmp_path / "result.png"
    make_cli_image(source)

    planned_code, planned_stdout, planned_stderr = run_cli(
        [
            "image-plan",
            str(source),
            str(plan_path),
            "--region",
            "25:20:55:35",
            "--json",
        ]
    )
    planned = json.loads(planned_stdout)
    acknowledgements = [
        item
        for code in planned["result"]["required_acknowledgements"]
        for item in ("--acknowledge", code)
    ]
    applied_code, applied_stdout, applied_stderr = run_cli(
        [
            "image-apply",
            str(source),
            str(plan_path),
            str(output),
            *acknowledgements,
            "--json",
        ]
    )

    applied = json.loads(applied_stdout)
    with Image.open(output) as result:
        result.load()
        assert result.format == "PNG"
        assert result.size == (80, 60)
    assert planned_code == ExitCode.SUCCESS
    assert planned_stderr == ""
    assert applied_code == ExitCode.SUCCESS
    assert applied_stderr == ""
    assert applied["result"]["plan_id"] == planned["result"]["plan_id"]
    assert applied["result"]["outside_changed_pixels"] == 0


def test_image_apply_requires_every_warning_acknowledgement(tmp_path: Path) -> None:
    source = tmp_path / "flat.png"
    plan_path = tmp_path / "plan.json"
    output = tmp_path / "result.png"
    make_cli_image(source, flat=True)
    run_cli(
        [
            "image-plan",
            str(source),
            str(plan_path),
            "--region",
            "0:0:60:50",
        ]
    )

    code, stdout, stderr = run_cli(
        ["image-apply", str(source), str(plan_path), str(output), "--json"]
    )

    payload = json.loads(stderr)
    assert code == ExitCode.ACKNOWLEDGEMENT_REQUIRED
    assert stdout == ""
    assert payload["error"]["code"] == "IMAGE_ACKNOWLEDGEMENT_REQUIRED"
    assert "IMAGE_MASK_OVER_25_PERCENT" in payload["error"]["message"]
    assert "IMAGE_LOW_CONTRAST_SELECTION" in payload["error"]["message"]
    assert not output.exists()


def test_image_apply_rejects_tampered_plan(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    plan_path = tmp_path / "plan.json"
    make_cli_image(source)
    run_cli(
        [
            "image-plan",
            str(source),
            str(plan_path),
            "--region",
            "25:20:55:35",
        ]
    )
    plan = json.loads(plan_path.read_text())
    plan["radius"] = 9
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    code, stdout, stderr = run_cli(
        [
            "image-apply",
            str(source),
            str(plan_path),
            str(tmp_path / "result.png"),
            "--json",
        ]
    )

    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert json.loads(stderr)["error"]["code"] == "IMAGE_PLAN_INTEGRITY_FAILED"


def test_image_apply_rejects_changed_source(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    plan_path = tmp_path / "plan.json"
    make_cli_image(source)
    run_cli(
        [
            "image-plan",
            str(source),
            str(plan_path),
            "--region",
            "25:20:55:35",
        ]
    )
    Image.new("RGB", (80, 60), "white").save(source, format="PNG")

    code, stdout, stderr = run_cli(
        [
            "image-apply",
            str(source),
            str(plan_path),
            str(tmp_path / "result.png"),
            "--json",
        ]
    )

    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert json.loads(stderr)["error"]["code"] == "IMAGE_PLAN_STALE"


def test_docx_plan_then_apply_removes_confirmed_candidate(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    plan_path = tmp_path / "docx-plan.json"
    output = tmp_path / "cleaned.docx"
    source.write_bytes(make_docx("DRAFT"))

    planned_code, planned_stdout, planned_stderr = run_cli(
        [
            "docx-plan",
            str(source),
            str(plan_path),
            "--watermark-text",
            "DRAFT",
            "--json",
        ]
    )
    planned = json.loads(planned_stdout)
    candidate = planned["result"]["candidates"][0]
    applied_code, applied_stdout, applied_stderr = run_cli(
        [
            "docx-apply",
            str(source),
            str(plan_path),
            str(output),
            "--candidate",
            candidate["candidate_id"],
            "--json",
        ]
    )

    applied = json.loads(applied_stdout)
    with ZipFile(output) as package:
        assert b"DRAFT" not in package.read("word/header1.xml")
    assert planned_code == ExitCode.SUCCESS
    assert planned_stderr == ""
    assert candidate["classification"] == "confirmed"
    assert applied_code == ExitCode.SUCCESS
    assert applied_stderr == ""
    assert applied["result"]["removed_count"] == 1
    assert applied["result"]["plan_id"] == planned["result"]["plan_id"]


def test_docx_apply_requires_candidate_level_acknowledgement(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    plan_path = tmp_path / "docx-plan.json"
    output = tmp_path / "cleaned.docx"
    source.write_bytes(make_docx("DRAFT"))
    _, stdout, _ = run_cli(
        ["docx-plan", str(source), str(plan_path), "--json"]
    )
    planned = json.loads(stdout)["result"]
    candidate_id = planned["candidates"][0]["candidate_id"]
    warning_code = planned["warnings"][0]["code"]

    rejected_code, rejected_stdout, rejected_stderr = run_cli(
        [
            "docx-apply",
            str(source),
            str(plan_path),
            str(output),
            "--candidate",
            candidate_id,
            "--json",
        ]
    )
    accepted_code, accepted_stdout, accepted_stderr = run_cli(
        [
            "docx-apply",
            str(source),
            str(plan_path),
            str(output),
            "--candidate",
            candidate_id,
            "--acknowledge",
            warning_code,
            "--json",
        ]
    )

    assert rejected_code == ExitCode.ACKNOWLEDGEMENT_REQUIRED
    assert rejected_stdout == ""
    assert json.loads(rejected_stderr)["error"]["code"] == (
        "DOCUMENT_ACKNOWLEDGEMENT_REQUIRED"
    )
    assert accepted_code == ExitCode.SUCCESS
    assert accepted_stderr == ""
    assert json.loads(accepted_stdout)["result"]["candidate_ids"] == [candidate_id]


def test_codecv_plan_then_apply_removes_pattern_and_preserves_text(
    tmp_path: Path,
) -> None:
    source = tmp_path / "resume.pdf"
    plan_path = tmp_path / "codecv-plan.json"
    output = tmp_path / "cleaned.pdf"
    source.write_bytes(make_codecv_pdf())

    planned_code, planned_stdout, planned_stderr = run_cli(
        ["codecv-plan", str(source), str(plan_path), "--json"]
    )
    planned = json.loads(planned_stdout)["result"]
    candidate_id = planned["candidates"][0]["candidate_id"]
    applied_code, applied_stdout, applied_stderr = run_cli(
        [
            "codecv-apply",
            str(source),
            str(plan_path),
            str(output),
            "--candidate",
            candidate_id,
            "--json",
        ]
    )
    _, rescanned_stdout, rescanned_stderr = run_cli(
        ["codecv-plan", str(output), str(tmp_path / "clean-plan.json"), "--json"]
    )

    applied = json.loads(applied_stdout)
    rescanned = json.loads(rescanned_stdout)["result"]
    assert planned_code == ExitCode.SUCCESS
    assert planned_stderr == ""
    assert planned["match_status"] == "matched"
    assert applied_code == ExitCode.SUCCESS
    assert applied_stderr == ""
    assert applied["result"]["removed_count"] == 1
    assert PdfReader(str(output)).pages[0].extract_text().strip() == "Resume body"
    assert rescanned_stderr == ""
    assert rescanned["match_status"] == "not_found"
    assert rescanned["candidate_count"] == 0


def test_document_apply_rejects_tampered_plan(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    plan_path = tmp_path / "docx-plan.json"
    source.write_bytes(make_docx("DRAFT"))
    run_cli(["docx-plan", str(source), str(plan_path)])
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["candidates"][0]["content"] = "CHANGED"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    code, stdout, stderr = run_cli(
        [
            "docx-apply",
            str(source),
            str(plan_path),
            str(tmp_path / "cleaned.docx"),
            "--candidate",
            payload["candidates"][0]["candidate_id"],
            "--json",
        ]
    )

    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert json.loads(stderr)["error"]["code"] == "DOCUMENT_PLAN_INTEGRITY_FAILED"


def test_document_apply_rejects_source_changed_after_plan(tmp_path: Path) -> None:
    source = tmp_path / "source.docx"
    plan_path = tmp_path / "docx-plan.json"
    source.write_bytes(make_docx("DRAFT"))
    _, planned_stdout, _ = run_cli(
        ["docx-plan", str(source), str(plan_path), "--json"]
    )
    candidate_id = json.loads(planned_stdout)["result"]["candidates"][0][
        "candidate_id"
    ]
    source.write_bytes(make_docx("FINAL"))

    code, stdout, stderr = run_cli(
        [
            "docx-apply",
            str(source),
            str(plan_path),
            str(tmp_path / "cleaned.docx"),
            "--candidate",
            candidate_id,
            "--json",
        ]
    )

    assert code == ExitCode.INPUT_INVALID
    assert stdout == ""
    assert json.loads(stderr)["error"]["code"] == "DOCUMENT_PLAN_STALE"
