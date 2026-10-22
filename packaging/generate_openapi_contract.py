from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src"
DEFAULT_OUTPUT = ROOT / "docs" / "release" / "openapi-v1.json"

if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from wmrm.api.app import create_app
from wmrm.settings import Settings


class OpenApiContractError(ValueError):
    pass


def build_contract() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="wmrm-openapi-") as temporary:
        app = create_app(
            Settings(
                data_dir=Path(temporary),
                docx_preview_enabled=False,
                pdf_preview_enabled=False,
                vlm_enabled=False,
            )
        )
        contract = app.openapi()
    paths = contract.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise OpenApiContractError("OpenAPI contract has no paths.")
    unexpected = sorted(path for path in paths if not path.startswith("/api/v1/"))
    if unexpected:
        raise OpenApiContractError(
            "Only versioned product API routes may enter the contract: " + ", ".join(unexpected)
        )
    return contract


def encoded_contract(contract: dict[str, Any]) -> str:
    return json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_contract(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded_contract(build_contract()), encoding="utf-8")


def check_contract(path: Path) -> None:
    if not path.is_file():
        raise OpenApiContractError(f"Committed OpenAPI contract is missing: {path}")
    expected = encoded_contract(build_contract())
    if path.read_text(encoding="utf-8") != expected:
        raise OpenApiContractError(
            "Committed OpenAPI contract is stale. Run `make api-contract` and review the diff."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify the deterministic FastAPI v1 contract."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_contract(args.output)
            print(f"OpenAPI contract verified: {args.output}")
        else:
            write_contract(args.output)
            print(f"OpenAPI contract generated: {args.output}")
    except OpenApiContractError as error:
        parser.exit(1, f"OpenAPI contract rejected: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
