from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import uuid
from enum import IntEnum
from pathlib import Path
from typing import TextIO, cast

from wmrm import __version__
from wmrm.adapters.documents.docx_editor import DocxEditError, remove_docx_candidates
from wmrm.adapters.images.inpaint import inpaint_image
from wmrm.adapters.pdf.codecv_editor import CodeCvEditError, remove_codecv_candidates
from wmrm.adapters.pdf.pymupdf_redaction import (
    LicenseMode,
    PdfRedactionError,
    probe_pymupdf,
    redact_pdf_regions,
)
from wmrm.adapters.pdf.raster_inpaint import (
    PdfRasterInpaintError,
    probe_tesseract,
    raster_inpaint_pdf_regions,
)
from wmrm.application.candidate_plan_files import (
    CandidatePlanFileError,
    create_candidate_plan,
    load_candidate_plan,
    revalidate_candidate_plan,
    select_candidates,
    serialize_candidate_plan,
)
from wmrm.application.image_plan_files import (
    ImagePlanFileError,
    create_image_plan,
    load_image_plan,
    revalidate_image_plan,
    serialize_image_plan,
)


class ExitCode(IntEnum):
    SUCCESS = 0
    USAGE = 2
    INPUT_INVALID = 3
    ACKNOWLEDGEMENT_REQUIRED = 4
    PROCESSING_FAILED = 5


class CliUsageError(Exception):
    pass


class CliError(Exception):
    def __init__(self, code: str, message: str, exit_code: ExitCode) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliUsageError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(
        prog="wmrm",
        description="Local-first watermark processing command line interface.",
    )
    parser.add_argument("--json", action="store_true", help="Emit one JSON object to stdout.")
    parser.add_argument("--version", action="version", version=f"wmrm {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor", help="Report local PDF and OCR runtime availability."
    )
    _add_json_flag(doctor)

    deep = subparsers.add_parser(
        "pdf-deep",
        help="Rasterize selected PDF pages, repair regions and restore searchable text.",
    )
    _add_json_flag(deep)
    _add_pdf_io(deep)
    deep.add_argument(
        "--region",
        action="append",
        required=True,
        type=_parse_pdf_region,
        metavar="PAGE:X0:Y0:X1:Y1",
        help="Crop-box-relative PDF points with a bottom-left origin; repeat as needed.",
    )
    deep.add_argument("--dpi", type=_bounded_int("DPI", 96, 300), default=144, metavar="DPI")
    deep.add_argument(
        "--radius", type=_bounded_int("radius", 1, 10), default=3, metavar="PIXELS"
    )
    deep.add_argument(
        "--ocr-languages", type=_parse_ocr_languages, default="eng", metavar="LANGS"
    )
    deep.add_argument(
        "--acknowledge-rasterization",
        action="store_true",
        help="Confirm selected pages lose links, forms and editable vector objects.",
    )

    redact = subparsers.add_parser(
        "pdf-redact",
        help="Physically remove PDF content intersecting selected regions.",
    )
    _add_json_flag(redact)
    _add_pdf_io(redact)
    redact.add_argument(
        "--region",
        action="append",
        required=True,
        type=_parse_pdf_region,
        metavar="PAGE:X0:Y0:X1:Y1",
        help="Crop-box-relative PDF points with a bottom-left origin; repeat as needed.",
    )
    redact.add_argument(
        "--acknowledge-content-removal",
        action="store_true",
        help="Confirm intersecting text, images, vectors and links may be removed.",
    )

    image_plan = subparsers.add_parser(
        "image-plan",
        help="Inspect image regions and save a reviewable inpainting plan.",
    )
    _add_json_flag(image_plan)
    image_plan.add_argument("input", type=Path, help="Source PNG, JPEG or WebP path.")
    image_plan.add_argument("plan", type=Path, help="New JSON plan path.")
    image_plan.add_argument(
        "--region",
        action="append",
        required=True,
        type=_parse_image_region,
        metavar="X0:Y0:X1:Y1",
        help="Display-pixel coordinates with a top-left origin; repeat as needed.",
    )
    image_plan.add_argument(
        "--radius", type=_bounded_int("radius", 1, 10), default=3, metavar="PIXELS"
    )
    image_plan.add_argument(
        "--force", action="store_true", help="Atomically replace an existing plan."
    )

    image_apply = subparsers.add_parser(
        "image-apply",
        help="Revalidate and execute a saved image inpainting plan.",
    )
    _add_json_flag(image_apply)
    image_apply.add_argument("input", type=Path, help="Source image referenced by the plan.")
    image_apply.add_argument("plan", type=Path, help="Reviewed JSON plan path.")
    image_apply.add_argument("output", type=Path, help="New lossless PNG path.")
    image_apply.add_argument(
        "--acknowledge",
        action="append",
        default=[],
        metavar="WARNING_CODE",
        help="Acknowledge a required warning code from the plan; repeat as needed.",
    )
    image_apply.add_argument(
        "--force", action="store_true", help="Atomically replace an existing output."
    )

    docx_plan = subparsers.add_parser(
        "docx-plan", help="Inspect DOCX watermark candidates and save a reviewable plan."
    )
    _add_candidate_plan_arguments(docx_plan, "DOCX")
    docx_plan.add_argument(
        "--watermark-text",
        help="Exact watermark text used to confirm matching Word watermark shapes.",
    )

    docx_apply = subparsers.add_parser(
        "docx-apply", help="Remove selected candidates from a reviewed DOCX plan."
    )
    _add_candidate_apply_arguments(docx_apply, "DOCX")

    codecv_plan = subparsers.add_parser(
        "codecv-plan", help="Inspect CodeCV PDF pattern candidates and save a reviewable plan."
    )
    _add_candidate_plan_arguments(codecv_plan, "CodeCV PDF")

    codecv_apply = subparsers.add_parser(
        "codecv-apply", help="Remove selected candidates from a reviewed CodeCV PDF plan."
    )
    _add_candidate_apply_arguments(codecv_apply, "CodeCV PDF")
    return parser


def _add_candidate_plan_arguments(parser: argparse.ArgumentParser, label: str) -> None:
    _add_json_flag(parser)
    parser.add_argument("input", type=Path, help=f"Source {label} path.")
    parser.add_argument("plan", type=Path, help="New JSON review-plan path.")
    parser.add_argument(
        "--force", action="store_true", help="Atomically replace an existing plan."
    )


def _add_candidate_apply_arguments(parser: argparse.ArgumentParser, label: str) -> None:
    _add_json_flag(parser)
    parser.add_argument("input", type=Path, help=f"Source {label} referenced by the plan.")
    parser.add_argument("plan", type=Path, help="Reviewed JSON plan path.")
    parser.add_argument("output", type=Path, help=f"New cleaned {label} path.")
    parser.add_argument(
        "--candidate",
        action="append",
        required=True,
        metavar="CANDIDATE_ID",
        help="Candidate ID from the plan; repeat to remove multiple candidates.",
    )
    parser.add_argument(
        "--acknowledge",
        action="append",
        default=[],
        metavar="WARNING_CODE",
        help="Candidate warning code from the plan; repeat as needed.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Atomically replace an existing output."
    )


def _add_pdf_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, help="Source PDF path.")
    parser.add_argument("output", type=Path, help="New PDF path.")
    parser.add_argument(
        "--license-mode",
        choices=("agpl", "commercial"),
        required=True,
        help="Explicitly select the license governing the installed PyMuPDF runtime.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing output file.")


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )


def _parse_pdf_region(value: str) -> dict[str, int | float]:
    parts = value.split(":")
    if len(parts) != 5:
        raise argparse.ArgumentTypeError("region must use PAGE:X0:Y0:X1:Y1")
    try:
        page_number = int(parts[0])
        x0, y0, x1, y1 = (float(item) for item in parts[1:])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("region contains a non-numeric value") from exc
    if (
        page_number < 1
        or not all(math.isfinite(item) for item in (x0, y0, x1, y1))
        or x0 < 0
        or y0 < 0
        or x0 >= x1
        or y0 >= y1
    ):
        raise argparse.ArgumentTypeError("region page and coordinates are invalid or reversed")
    return {
        "page_number": page_number,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
    }


def _parse_image_region(value: str) -> dict[str, float]:
    parts = value.split(":")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("region must use X0:Y0:X1:Y1")
    try:
        x0, y0, x1, y1 = (float(item) for item in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("region contains a non-numeric value") from exc
    if (
        not all(math.isfinite(item) for item in (x0, y0, x1, y1))
        or x0 < 0
        or y0 < 0
        or x0 >= x1
        or y0 >= y1
    ):
        raise argparse.ArgumentTypeError("region coordinates are invalid or reversed")
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _bounded_int(label: str, minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{label} must be an integer") from exc
        if not minimum <= parsed <= maximum:
            raise argparse.ArgumentTypeError(
                f"{label} must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def _parse_ocr_languages(value: str) -> str:
    if not 1 <= len(value) <= 80 or re.fullmatch(r"[A-Za-z0-9_+-]+", value) is None:
        raise argparse.ArgumentTypeError(
            "OCR languages must contain only letters, digits, _, + or -"
        )
    return value


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr
    json_mode = "--json" in arguments
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
        json_mode = bool(args.json)
        result = _run(args)
    except CliUsageError as exc:
        return _emit_error(
            "INVALID_USAGE",
            str(exc),
            ExitCode.USAGE,
            json_mode=json_mode,
            stream=error_stream,
        )
    except CliError as exc:
        return _emit_error(
            exc.code,
            str(exc),
            exc.exit_code,
            json_mode=json_mode,
            stream=error_stream,
        )
    except (PdfRedactionError, PdfRasterInpaintError, DocxEditError, CodeCvEditError) as exc:
        return _emit_error(
            "PROCESSING_FAILED",
            str(exc),
            ExitCode.PROCESSING_FAILED,
            json_mode=json_mode,
            stream=error_stream,
        )
    except ImagePlanFileError as exc:
        return _emit_error(
            exc.code,
            str(exc),
            ExitCode.INPUT_INVALID,
            json_mode=json_mode,
            stream=error_stream,
        )
    except CandidatePlanFileError as exc:
        exit_code = (
            ExitCode.ACKNOWLEDGEMENT_REQUIRED
            if exc.code == "DOCUMENT_ACKNOWLEDGEMENT_REQUIRED"
            else ExitCode.INPUT_INVALID
        )
        return _emit_error(
            exc.code,
            str(exc),
            exit_code,
            json_mode=json_mode,
            stream=error_stream,
        )
    except ValueError as exc:
        return _emit_error(
            "PROCESSING_FAILED",
            str(exc),
            ExitCode.PROCESSING_FAILED,
            json_mode=json_mode,
            stream=error_stream,
        )
    _emit_success(args.command, result, json_mode=json_mode, stream=output_stream)
    return int(ExitCode.SUCCESS)


def _run(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "doctor":
        return {
            "version": __version__,
            "pymupdf": probe_pymupdf().to_dict(),
            "tesseract": probe_tesseract(),
        }

    if args.command == "image-plan":
        source = _resolve_input(args.input, "Image")
        plan_path = _validate_output_target(source, args.plan, {".json"}, args.force)
        plan = create_image_plan(source, list(args.region), args.radius)
        generated = _temporary_sibling(plan_path)
        try:
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_text(serialize_image_plan(plan), encoding="utf-8")
            _finalize_output(generated, plan_path)
        except OSError as exc:
            generated.unlink(missing_ok=True)
            raise CliError(
                "OUTPUT_WRITE_FAILED",
                f"Image plan could not be written: {plan_path}",
                ExitCode.PROCESSING_FAILED,
            ) from exc
        return {
            "output": str(plan_path),
            "plan_id": plan.plan_id,
            "coverage_ratio": plan.coverage_ratio,
            "complexity": plan.complexity.level,
            "required_acknowledgements": plan.required_acknowledgements,
            "warnings": [item.model_dump(mode="json") for item in plan.warnings],
        }

    if args.command == "image-apply":
        source = _resolve_input(args.input, "Image")
        plan_path = _resolve_input(args.plan, "Image plan")
        if plan_path.suffix.casefold() != ".json":
            raise CliError(
                "IMAGE_PLAN_INVALID", "Image plan must use a .json suffix.", ExitCode.INPUT_INVALID
            )
        plan = revalidate_image_plan(source, load_image_plan(plan_path))
        acknowledged = set(args.acknowledge)
        known_codes = {item.code for item in plan.warnings}
        unknown = sorted(acknowledged - known_codes)
        if unknown:
            raise CliError(
                "IMAGE_ACKNOWLEDGEMENT_INVALID",
                "Unknown acknowledgement codes: " + ", ".join(unknown),
                ExitCode.INPUT_INVALID,
            )
        missing = sorted(set(plan.required_acknowledgements) - acknowledged)
        if missing:
            raise CliError(
                "IMAGE_ACKNOWLEDGEMENT_REQUIRED",
                "Required acknowledgement codes: " + ", ".join(missing),
                ExitCode.ACKNOWLEDGEMENT_REQUIRED,
            )
        output = _validate_output_target(source, args.output, {".png"}, args.force)
        processing_output = _processing_output(output, args.force)
        result = inpaint_image(
            source,
            processing_output,
            [
                {"x0": item.x0, "y0": item.y0, "x1": item.x1, "y1": item.y1}
                for item in plan.regions
            ],
            plan.radius,
        )
        _finalize_output(processing_output, output)
        return {"output": str(output), "plan_id": plan.plan_id, **result}

    if args.command in {"docx-plan", "codecv-plan"}:
        source = _resolve_input(args.input, "Document")
        plan_path = _validate_output_target(source, args.plan, {".json"}, args.force)
        plan_kind = "docx" if args.command == "docx-plan" else "codecv"
        plan = create_candidate_plan(
            source,
            plan_kind,
            watermark_text=getattr(args, "watermark_text", None),
        )
        _write_plan_file(plan_path, serialize_candidate_plan(plan))
        return {
            "output": str(plan_path),
            "plan_id": plan.plan_id,
            "source_kind": plan.source_kind,
            "match_status": plan.match_status,
            "candidate_count": len(plan.candidates),
            "candidates": [item.model_dump(mode="json") for item in plan.candidates],
            "warnings": [item.model_dump(mode="json") for item in plan.warnings],
            "scan_warnings": plan.scan_warnings,
        }

    if args.command in {"docx-apply", "codecv-apply"}:
        source = _resolve_input(args.input, "Document")
        plan_path = _resolve_input(args.plan, "Document plan")
        if plan_path.suffix.casefold() != ".json":
            raise CandidatePlanFileError(
                "DOCUMENT_PLAN_INVALID", "Document plan must use a .json suffix."
            )
        plan = revalidate_candidate_plan(source, load_candidate_plan(plan_path))
        expected_kind = (
            "docx_object_removal"
            if args.command == "docx-apply"
            else "codecv_object_removal"
        )
        if plan.kind != expected_kind:
            raise CandidatePlanFileError(
                "DOCUMENT_PLAN_KIND_MISMATCH",
                f"Plan kind {plan.kind} cannot be used by {args.command}.",
            )
        selected = select_candidates(plan, list(args.candidate), list(args.acknowledge))
        suffix = ".docx" if args.command == "docx-apply" else ".pdf"
        output = _validate_output_target(source, args.output, {suffix}, args.force)
        processing_output = _processing_output(output, args.force)
        candidate_payload = [item.model_dump(mode="json") for item in selected]
        if args.command == "docx-apply":
            result = remove_docx_candidates(source, processing_output, candidate_payload)
        else:
            result = remove_codecv_candidates(source, processing_output, candidate_payload)
        _finalize_output(processing_output, output)
        return {
            "output": str(output),
            "plan_id": plan.plan_id,
            "candidate_ids": [item.candidate_id for item in selected],
            **result,
        }

    source, output = _validate_pdf_paths(args.input, args.output, args.force)
    regions = list(args.region)
    license_mode = cast(LicenseMode, args.license_mode)
    if args.command == "pdf-deep":
        if not args.acknowledge_rasterization:
            raise CliError(
                "RASTERIZATION_ACKNOWLEDGEMENT_REQUIRED",
                "pdf-deep requires --acknowledge-rasterization.",
                ExitCode.ACKNOWLEDGEMENT_REQUIRED,
            )
        processing_output = _processing_output(output, args.force)
        result = raster_inpaint_pdf_regions(
            source,
            processing_output,
            regions,
            license_mode=license_mode,
            dpi=args.dpi,
            radius=args.radius,
            ocr_languages=args.ocr_languages,
        )
        _finalize_output(processing_output, output)
    elif args.command == "pdf-redact":
        if not args.acknowledge_content_removal:
            raise CliError(
                "CONTENT_REMOVAL_ACKNOWLEDGEMENT_REQUIRED",
                "pdf-redact requires --acknowledge-content-removal.",
                ExitCode.ACKNOWLEDGEMENT_REQUIRED,
            )
        processing_output = _processing_output(output, args.force)
        result = redact_pdf_regions(
            source,
            processing_output,
            regions,
            license_mode=license_mode,
        )
        _finalize_output(processing_output, output)
    else:
        raise CliError("UNKNOWN_COMMAND", str(args.command), ExitCode.USAGE)
    return {"output": str(output), **result}


def _resolve_input(input_path: Path, label: str) -> Path:
    try:
        source = input_path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise CliError(
            "INPUT_NOT_FOUND", f"{label} is unavailable: {input_path}", ExitCode.INPUT_INVALID
        ) from exc
    if not source.is_file():
        raise CliError("INPUT_INVALID", f"{label} must be a file.", ExitCode.INPUT_INVALID)
    return source


def _validate_pdf_paths(
    input_path: Path, output_path: Path, force: bool
) -> tuple[Path, Path]:
    source = _resolve_input(input_path, "Input PDF")
    if source.suffix.casefold() != ".pdf":
        raise CliError("INPUT_INVALID", "Input must be a PDF file.", ExitCode.INPUT_INVALID)
    output = _validate_output_target(source, output_path, {".pdf"}, force)
    return source, output


def _validate_output_target(
    source: Path, output_path: Path, suffixes: set[str], force: bool
) -> Path:
    expanded_output = output_path.expanduser()
    if expanded_output.is_symlink():
        raise CliError(
            "OUTPUT_INVALID",
            "Output cannot be a symlink.",
            ExitCode.INPUT_INVALID,
        )
    output = expanded_output.resolve(strict=False)
    if output.suffix.casefold() not in suffixes:
        expected = ", ".join(sorted(suffixes))
        raise CliError(
            "OUTPUT_INVALID", f"Output must use one of: {expected}.", ExitCode.INPUT_INVALID
        )
    if source == output:
        raise CliError(
            "OUTPUT_OVERWRITES_INPUT",
            "Output must be different from the source file.",
            ExitCode.INPUT_INVALID,
        )
    if output.exists() and not force:
        raise CliError(
            "OUTPUT_EXISTS",
            "Output already exists; pass --force to replace it.",
            ExitCode.INPUT_INVALID,
        )
    if output.exists() and not output.is_file():
        raise CliError(
            "OUTPUT_INVALID",
            "Existing output must be a regular file.",
            ExitCode.INPUT_INVALID,
        )
    return output


def _processing_output(output: Path, force: bool) -> Path:
    if output.exists() and force:
        return output.with_name(f".{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix}")
    return output


def _temporary_sibling(output: Path) -> Path:
    return output.with_name(f".{output.stem}.{uuid.uuid4().hex}.tmp{output.suffix}")


def _write_plan_file(output: Path, content: str) -> None:
    generated = _temporary_sibling(output)
    try:
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.write_text(content, encoding="utf-8")
        _finalize_output(generated, output)
    except CliError:
        raise
    except OSError as exc:
        try:
            generated.unlink(missing_ok=True)
        except OSError:
            pass
        raise CliError(
            "OUTPUT_WRITE_FAILED",
            f"Plan could not be written: {output}",
            ExitCode.PROCESSING_FAILED,
        ) from exc


def _finalize_output(generated: Path, output: Path) -> None:
    if generated == output:
        return
    try:
        os.replace(generated, output)
    except OSError as exc:
        try:
            generated.unlink(missing_ok=True)
        except OSError:
            pass
        raise CliError(
            "OUTPUT_WRITE_FAILED",
            f"Generated output could not replace: {output}",
            ExitCode.PROCESSING_FAILED,
        ) from exc


def _emit_success(
    command: str, result: dict[str, object], *, json_mode: bool, stream: TextIO
) -> None:
    if json_mode:
        print(
            json.dumps(
                {"ok": True, "command": command, "result": result},
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=stream,
        )
        return
    if command == "doctor":
        print(f"wmrm {result['version']}", file=stream)
        print(f"PyMuPDF available: {result['pymupdf']['available']}", file=stream)  # type: ignore[index]
        print(f"Tesseract available: {result['tesseract']['available']}", file=stream)  # type: ignore[index]
        return
    print(f"Completed {command}: {result['output']}", file=stream)


def _emit_error(
    code: str,
    message: str,
    exit_code: ExitCode,
    *,
    json_mode: bool,
    stream: TextIO,
) -> int:
    if json_mode:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {"code": code, "message": message},
                    "exit_code": int(exit_code),
                },
                ensure_ascii=True,
                sort_keys=True,
            ),
            file=stream,
        )
    else:
        print(f"wmrm: {code}: {message}", file=stream)
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
