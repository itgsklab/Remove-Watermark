from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "backend" / "src" / "wmrm"
DEFAULT_OUTPUT = ROOT / "docs" / "release" / "error-codes-v1.json"
CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+$")
EXIT_CODES = {
    "SUCCESS": 0,
    "USAGE": 2,
    "INPUT_INVALID": 3,
    "ACKNOWLEDGEMENT_REQUIRED": 4,
    "PROCESSING_FAILED": 5,
}
API_FIXED_CODES = {
    "CROSS_ORIGIN_REQUEST": ("response", (403,), SOURCE_ROOT / "api" / "app.py"),
    "INVALID_REQUEST": ("response", (422,), SOURCE_ROOT / "api" / "app.py"),
    "NOT_FOUND": ("response", (404,), SOURCE_ROOT / "api" / "frontend.py"),
    "TASK_START_FAILED": ("task", (), SOURCE_ROOT / "application" / "tasks.py"),
    "PROCESSING_FAILED": ("task", (), SOURCE_ROOT / "application" / "tasks.py"),
    "UNKNOWN": ("task", (), SOURCE_ROOT / "application" / "tasks.py"),
}
CLI_PROPAGATED_ASSET_MODULES = (
    SOURCE_ROOT / "adapters" / "documents" / "docx.py",
    SOURCE_ROOT / "adapters" / "images" / "metadata.py",
    SOURCE_ROOT / "adapters" / "pdf" / "codecv.py",
)


class ErrorCodeContractError(ValueError):
    pass


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _literal_code(node: ast.Call, path: Path) -> str | None:
    if not node.args:
        raise ErrorCodeContractError(f"{path}:{node.lineno} has no error code argument.")
    value = node.args[0]
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return None
    code = value.value
    if not CODE_PATTERN.fullmatch(code):
        raise ErrorCodeContractError(f"{path}:{node.lineno} has invalid error code {code!r}.")
    return code


def _status_code(node: ast.Call, *, default: int, path: Path) -> int:
    value: ast.expr | None = node.args[2] if len(node.args) >= 3 else None
    for keyword in node.keywords:
        if keyword.arg == "status_code":
            value = keyword.value
    if value is None:
        return default
    if not isinstance(value, ast.Constant) or not isinstance(value.value, int):
        raise ErrorCodeContractError(
            f"{path}:{node.lineno} must use a literal public HTTP status."
        )
    if value.value < 400 or value.value > 599:
        raise ErrorCodeContractError(f"{path}:{node.lineno} has invalid HTTP status.")
    return value.value


def _exit_code(node: ast.Call, path: Path) -> int:
    if len(node.args) < 3:
        raise ErrorCodeContractError(f"{path}:{node.lineno} has no CLI exit code.")
    value = node.args[2]
    if not (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "ExitCode"
        and value.attr in EXIT_CODES
    ):
        raise ErrorCodeContractError(
            f"{path}:{node.lineno} must use a declared literal ExitCode member."
        )
    return EXIT_CODES[value.attr]


def _trees() -> dict[Path, ast.Module]:
    trees: dict[Path, ast.Module] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if "vendor" in path.parts or "benchmarks" in path.parts:
            continue
        trees[path] = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return trees


def _asset_codes(tree: ast.Module, path: Path) -> dict[str, set[int]]:
    rows: dict[str, set[int]] = defaultdict(set)
    defaults = {"AssetError": 400, "XiaohongshuLinkError": 422}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_name(node) not in defaults:
            continue
        name = _call_name(node)
        code = _literal_code(node, path)
        if code is None:
            raise ErrorCodeContractError(
                f"{path}:{node.lineno} dynamically constructs a public API error code."
            )
        rows[code].add(_status_code(node, default=defaults[name], path=path))
    return rows


def build_contract() -> dict[str, Any]:
    trees = _trees()
    api: dict[str, dict[str, Any]] = {}
    all_asset_codes: dict[Path, dict[str, set[int]]] = {}
    for path, tree in trees.items():
        found = _asset_codes(tree, path)
        all_asset_codes[path] = found
        for code, statuses in found.items():
            row = api.setdefault(code, {"delivery": "response", "http_statuses": set()})
            row["http_statuses"].update(statuses)

    for code, (delivery, statuses, path) in API_FIXED_CODES.items():
        if f'"{code}"' not in path.read_text(encoding="utf-8"):
            raise ErrorCodeContractError(f"Expected public code {code} is missing from {path}.")
        row = api.setdefault(code, {"delivery": delivery, "http_statuses": set()})
        if row["delivery"] != delivery:
            raise ErrorCodeContractError(f"Public code {code} uses conflicting delivery modes.")
        row["http_statuses"].update(statuses)

    cli: dict[str, set[int]] = defaultdict(set)
    cli_path = SOURCE_ROOT / "cli.py"
    plan_errors = {
        "ImagePlanFileError": 3,
        "CandidatePlanFileError": 3,
    }
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "CliError":
                code = _literal_code(node, path)
                if code is not None:
                    cli[code].add(_exit_code(node, path))
            elif name in plan_errors:
                code = _literal_code(node, path)
                if code is not None:
                    exit_code = 4 if code == "DOCUMENT_ACKNOWLEDGEMENT_REQUIRED" else 3
                    cli[code].add(exit_code)
            elif name == "_emit_error" and path == cli_path:
                code = _literal_code(node, path)
                if code is not None:
                    cli[code].add(_exit_code(node, path))

    for path in CLI_PROPAGATED_ASSET_MODULES:
        for code in all_asset_codes[path]:
            cli[code].add(3)

    return {
        "contract_version": 1,
        "api_version": "v1",
        "api_error_codes": [
            {
                "code": code,
                "delivery": row["delivery"],
                "http_statuses": sorted(row["http_statuses"]),
            }
            for code, row in sorted(api.items())
        ],
        "cli_error_codes": [
            {"code": code, "exit_codes": sorted(exit_codes)}
            for code, exit_codes in sorted(cli.items())
        ],
    }


def encoded_contract(contract: dict[str, Any]) -> str:
    return json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_contract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded_contract(build_contract()), encoding="utf-8")


def check_contract(path: Path) -> None:
    if not path.is_file():
        raise ErrorCodeContractError(f"Committed error-code contract is missing: {path}")
    if path.read_text(encoding="utf-8") != encoded_contract(build_contract()):
        raise ErrorCodeContractError(
            "Committed error-code contract is stale. Run `make error-contract` and review the diff."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify public v1 error codes.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_contract(args.output)
            print(f"Error-code contract verified: {args.output}")
        else:
            write_contract(args.output)
            print(f"Error-code contract generated: {args.output}")
    except ErrorCodeContractError as error:
        parser.exit(1, f"Error-code contract rejected: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
