from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import venv
from zipfile import ZipFile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONSTRAINTS = ROOT / "packaging" / "constraints.txt"
CLI_CONTRACT = ROOT / "packaging" / "cli-contract-v1.json"


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_license_payload(wheel: Path) -> None:
    expected = (BACKEND / "LICENSE").read_bytes()
    with ZipFile(wheel) as archive:
        matches = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/licenses/LICENSE")
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"Expected one packaged AGPL license file, found {len(matches)}."
            )
        if archive.read(matches[0]) != expected:
            raise RuntimeError("Packaged AGPL license does not match backend/LICENSE.")


def git_value(*arguments: str) -> str:
    return subprocess.check_output(
        ["git", *arguments], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def run_json(command: list[str], *, cwd: Path, env: dict[str, str]) -> dict:
    print("+", " ".join(command))
    completed = subprocess.run(
        command, cwd=cwd, env=env, check=False, capture_output=True, text=True
    )
    if completed.returncode:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no command output"
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {detail}"
        )
    print(completed.stdout, end="")
    return json.loads(completed.stdout)


def assert_success_contract(payload: dict, contract: dict, command: str) -> None:
    if set(payload) != set(contract["success_envelope_keys"]):
        raise RuntimeError(f"{command} changed the v1 success envelope.")
    if payload.get("ok") is not True or payload.get("command") != command:
        raise RuntimeError(f"{command} returned an invalid success envelope.")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise TypeError(f"{command} result must be an object.")
    missing = sorted(set(contract["commands"][command]) - set(result))
    if missing:
        raise RuntimeError(f"{command} omitted v1 result keys: {', '.join(missing)}")


def run_cli_json(
    cli: Path,
    contract: dict,
    command: str,
    arguments: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict:
    payload = run_json([str(cli), command, *arguments, "--json"], cwd=cwd, env=env)
    assert_success_contract(payload, contract, command)
    return payload


def assert_plan_contract(path: Path, contract: dict, kind: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != kind:
        raise RuntimeError(f"Expected {kind} plan, received {payload.get('kind')!r}.")
    if payload.get("schema_version") != contract["plan_schemas"][kind]:
        raise RuntimeError(f"{kind} plan schema changed without a contract version bump.")


def assert_error_contract(
    cli: Path,
    contract: dict,
    arguments: list[str],
    expected_exit_code: int,
    *,
    cwd: Path,
    env: dict[str, str],
) -> dict:
    failure = subprocess.run(
        [str(cli), "--json", *arguments],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if failure.returncode != expected_exit_code or failure.stdout:
        raise RuntimeError("CLI error stream or exit code changed.")
    payload = json.loads(failure.stderr)
    if set(payload) != set(contract["error_envelope_keys"]):
        raise RuntimeError("CLI changed the v1 error envelope.")
    if (
        payload.get("ok") is not False
        or payload.get("exit_code") != expected_exit_code
        or set(payload.get("error", {})) != set(contract["error_body_keys"])
    ):
        raise RuntimeError("CLI returned an invalid v1 error envelope.")
    return payload


def venv_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def venv_script(directory: Path, name: str) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / f"{name}.exe"
    return directory / "bin" / name


def verify_docx_cli(
    cli: Path, python: Path, work: Path, env: dict[str, str], contract: dict
) -> None:
    source = work / "wheel-source.docx"
    plan = work / "wheel-docx-plan.json"
    output = work / "wheel-docx-result.docx"
    fixture = f"""
from zipfile import ZIP_DEFLATED, ZipFile

with ZipFile({str(source)!r}, "w", ZIP_DEFLATED) as package:
    package.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
    package.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>')
    package.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    package.writestr("word/header1.xml", '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:v="urn:schemas-microsoft-com:vml"><w:p><w:r><w:pict><v:shape id="Watermark1" type="#_x0000_t136"><v:textpath string="DRAFT"/></v:shape></w:pict></w:r></w:p></w:hdr>')
    package.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/></Relationships>')
"""
    run([str(python), "-I", "-c", fixture], cwd=work, env=env)
    planned = run_cli_json(
        cli,
        contract,
        "docx-plan",
        [
            str(source),
            str(plan),
            "--watermark-text",
            "DRAFT",
        ],
        cwd=work,
        env=env,
    )
    assert_plan_contract(plan, contract, "docx_object_removal")
    candidate_id = planned["result"]["candidates"][0]["candidate_id"]
    run_cli_json(
        cli,
        contract,
        "docx-apply",
        [
            str(source),
            str(plan),
            str(output),
            "--candidate",
            candidate_id,
        ],
        cwd=work,
        env=env,
    )
    if not output.is_file():
        raise RuntimeError("Installed CLI did not produce the DOCX artifact.")


def verify_codecv_cli(
    cli: Path, python: Path, work: Path, env: dict[str, str], contract: dict
) -> None:
    source = work / "wheel-codecv.pdf"
    plan = work / "wheel-codecv-plan.json"
    output = work / "wheel-codecv-result.pdf"
    fixture = f"""
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject

writer = PdfWriter()
page = writer.add_blank_page(width=612, height=792)
font = DictionaryObject({{NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}})
pattern = DecodedStreamObject()
pattern.set_data(b"0.92 g 0 0 30 30 re f\\n")
pattern.update({{NameObject("/Type"): NameObject("/Pattern"), NameObject("/PatternType"): NumberObject(1), NameObject("/PaintType"): NumberObject(1), NameObject("/TilingType"): NumberObject(1), NameObject("/BBox"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(30), FloatObject(30)]), NameObject("/XStep"): FloatObject(30), NameObject("/YStep"): FloatObject(30), NameObject("/Resources"): DictionaryObject()}})
resources = DictionaryObject({{NameObject("/Font"): DictionaryObject({{NameObject("/F1"): writer._add_object(font)}}), NameObject("/Pattern"): DictionaryObject({{NameObject("/Watermark1"): writer._add_object(pattern)}})}})
content = DecodedStreamObject()
content.set_data(b"BT /F1 12 Tf 72 720 Td (Resume body) Tj ET\\n/Pattern CS /Pattern cs /Watermark1 SCN /Watermark1 scn 0 0 612 792 re f\\n")
page[NameObject("/Resources")] = resources
page[NameObject("/Contents")] = writer._add_object(content)
with open({str(source)!r}, "wb") as handle:
    writer.write(handle)
"""
    run([str(python), "-I", "-c", fixture], cwd=work, env=env)
    planned = run_cli_json(
        cli,
        contract,
        "codecv-plan",
        [str(source), str(plan)],
        cwd=work,
        env=env,
    )
    assert_plan_contract(plan, contract, "codecv_object_removal")
    candidate_id = planned["result"]["candidates"][0]["candidate_id"]
    run_cli_json(
        cli,
        contract,
        "codecv-apply",
        [
            str(source),
            str(plan),
            str(output),
            "--candidate",
            candidate_id,
        ],
        cwd=work,
        env=env,
    )
    if not output.is_file():
        raise RuntimeError("Installed CLI did not produce the CodeCV PDF artifact.")


def verify_pdf_cli(
    cli: Path, python: Path, work: Path, env: dict[str, str], contract: dict
) -> None:
    source = work / "wheel-general.pdf"
    redacted = work / "wheel-redacted.pdf"
    repaired = work / "wheel-deep.pdf"
    fixture = (
        "from pathlib import Path; "
        "from wmrm.benchmarks.pdf_redaction_probe import _fixture_pdf; "
        f"Path({str(source)!r}).write_bytes(_fixture_pdf())"
    )
    run([str(python), "-I", "-c", fixture], cwd=work, env=env)
    region = "1:90:680:245:735"
    assert_error_contract(
        cli,
        contract,
        [
            "pdf-redact",
            str(source),
            str(work / "unacknowledged.pdf"),
            "--region",
            region,
            "--license-mode",
            "agpl",
        ],
        contract["exit_codes"]["acknowledgement_required"],
        cwd=work,
        env=env,
    )
    corrupt = work / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\ntruncated")
    assert_error_contract(
        cli,
        contract,
        [
            "pdf-redact",
            str(corrupt),
            str(work / "failed.pdf"),
            "--region",
            region,
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
        ],
        contract["exit_codes"]["processing_failed"],
        cwd=work,
        env=env,
    )
    run_cli_json(
        cli,
        contract,
        "pdf-redact",
        [
            str(source),
            str(redacted),
            "--region",
            region,
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
        ],
        cwd=work,
        env=env,
    )
    run_cli_json(
        cli,
        contract,
        "pdf-deep",
        [
            str(source),
            str(repaired),
            "--region",
            region,
            "--license-mode",
            "agpl",
            "--dpi",
            "96",
            "--acknowledge-rasterization",
        ],
        cwd=work,
        env=env,
    )
    verify = f"""
from pypdf import PdfReader

for path in ({str(redacted)!r}, {str(repaired)!r}):
    reader = PdfReader(path, strict=True)
    assert len(reader.pages) == 2
    first = reader.pages[0].extract_text() or ""
    second = reader.pages[1].extract_text() or ""
    assert "REMOVE-ME" not in first
    assert "KEEP-ME" in first
    assert "PAGE-TWO" in second
"""
    run([str(python), "-I", "-c", verify], cwd=work, env=env)


def verify_contract_surface(
    cli: Path, work: Path, env: dict[str, str], contract: dict
) -> None:
    help_result = subprocess.run(
        [str(cli), "--help"],
        cwd=work,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    missing_commands = sorted(
        command for command in contract["commands"] if command not in help_result.stdout
    )
    if missing_commands:
        raise RuntimeError("Installed CLI omitted commands: " + ", ".join(missing_commands))

    assert_error_contract(
        cli,
        contract,
        ["pdf-redact"],
        contract["exit_codes"]["usage"],
        cwd=work,
        env=env,
    )
    assert_error_contract(
        cli,
        contract,
        [
            "pdf-redact",
            str(work / "missing.pdf"),
            str(work / "unused.pdf"),
            "--region",
            "1:0:0:10:10",
            "--license-mode",
            "agpl",
            "--acknowledge-content-removal",
        ],
        contract["exit_codes"]["input_invalid"],
        cwd=work,
        env=env,
    )


def load_contract() -> dict:
    contract = json.loads(CLI_CONTRACT.read_text(encoding="utf-8"))
    if contract.get("contract_version") != 1:
        raise RuntimeError("Unsupported CLI contract version.")
    if contract.get("target_public_version") != "0.1.0":
        raise RuntimeError("The v1 contract must target the first public 0.1.0 release.")
    return contract


def write_evidence_report(
    path: Path,
    contract: dict,
    wheel: Path,
) -> None:
    commit = os.environ.get("GITHUB_SHA") or git_value("rev-parse", "HEAD")
    payload = {
        "schema_version": 1,
        "status": "passed",
        "verified_at": datetime.now(UTC).isoformat(),
        "source_commit": commit,
        "source_dirty": bool(git_value("status", "--porcelain")),
        "contract": {
            "version": contract["contract_version"],
            "sha256": sha256(CLI_CONTRACT),
            "target_public_version": contract["target_public_version"],
        },
        "package": {
            "version": contract["development_version"],
            "wheel": wheel.name,
            "wheel_sha256": sha256(wheel),
        },
        "runtime": {
            "system": platform.system(),
            "release": platform.release(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "verified": {
            "commands": sorted(contract["commands"]),
            "exit_codes": sorted(contract["exit_codes"].values()),
            "plan_schemas": contract["plan_schemas"],
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the backend wheel and verify it in a new virtual environment."
    )
    parser.add_argument(
        "--keep-work",
        type=Path,
        help="Keep intermediate wheel and virtual environment files in this directory.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="Write source-input, runtime and verified-contract evidence after success.",
    )
    args = parser.parse_args()
    contract = load_contract()

    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required")

    temporary = None
    if args.keep_work:
        work = args.keep_work.resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="wmrm-wheel-check-")
        work = Path(temporary.name)

    wheels = work / "wheels"
    environment = work / "venv"
    wheels.mkdir(parents=True, exist_ok=True)
    run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), "."],
        cwd=BACKEND,
    )
    built = sorted(wheels.glob("wmrm-*.whl"))
    if len(built) != 1:
        raise SystemExit(f"Expected one wmrm wheel, found {len(built)}")
    verify_license_payload(built[0])

    venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    python = venv_python(environment)
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--constraint",
            str(CONSTRAINTS),
            str(built[0]),
        ],
        cwd=work,
        env=clean_env,
    )
    run([str(python), "-m", "pip", "check"], cwd=work, env=clean_env)
    probe = (
        "import importlib.metadata as m; "
        "from wmrm.api.app import create_app; "
        "app=create_app(); "
        "assert app.title == 'Watermark Remover'; "
        f"assert m.version('wmrm') == {contract['development_version']!r}; "
        "print('wheel import probe: ok')"
    )
    run([str(python), "-I", "-c", probe], cwd=work, env=clean_env)
    cli = venv_script(environment, "wmrm")
    verify_contract_surface(cli, work, clean_env, contract)
    doctor = run_cli_json(
        cli,
        contract,
        "doctor",
        [],
        cwd=work,
        env=clean_env,
    )
    if doctor["result"]["version"] != contract["development_version"]:
        raise RuntimeError("Installed CLI version does not match the v1 contract development line.")
    source_image = work / "wheel-image.png"
    image_plan = work / "wheel-image-plan.json"
    output_image = work / "wheel-image-result.png"
    fixture = (
        "from PIL import Image, ImageDraw; "
        f"p={str(source_image)!r}; "
        "im=Image.new('RGB',(80,60),'#d2b48c'); "
        "ImageDraw.Draw(im).rectangle((25,20,54,34),fill='#332211'); "
        "im.save(p,format='PNG')"
    )
    run([str(python), "-I", "-c", fixture], cwd=work, env=clean_env)
    planned = run_cli_json(
        cli,
        contract,
        "image-plan",
        [
            str(source_image),
            str(image_plan),
            "--region",
            "25:20:55:35",
        ],
        cwd=work,
        env=clean_env,
    )
    assert_plan_contract(image_plan, contract, "image_inpaint")
    acknowledgements = [
        value
        for code in planned["result"]["required_acknowledgements"]
        for value in ("--acknowledge", code)
    ]
    run_cli_json(
        cli,
        contract,
        "image-apply",
        [
            str(source_image),
            str(image_plan),
            str(output_image),
            *acknowledgements,
        ],
        cwd=work,
        env=clean_env,
    )
    if not output_image.is_file():
        raise RuntimeError("Installed CLI did not produce the image artifact.")
    verify_docx_cli(cli, python, work, clean_env, contract)
    verify_codecv_cli(cli, python, work, clean_env, contract)
    verify_pdf_cli(cli, python, work, clean_env, contract)
    if args.report_json:
        write_evidence_report(args.report_json.resolve(), contract, built[0])
    print(f"clean wheel installation verified: {built[0].name}")
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
