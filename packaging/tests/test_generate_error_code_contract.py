from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "generate_error_code_contract.py"
SPEC = importlib.util.spec_from_file_location("generate_error_code_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_contract_is_deterministic_sorted_and_covers_public_surfaces() -> None:
    first = MODULE.build_contract()
    second = MODULE.build_contract()

    assert first == second
    assert first["contract_version"] == 1
    assert first["api_version"] == "v1"
    api_codes = [row["code"] for row in first["api_error_codes"]]
    cli_codes = [row["code"] for row in first["cli_error_codes"]]
    assert api_codes == sorted(set(api_codes))
    assert cli_codes == sorted(set(cli_codes))
    assert {"INVALID_REQUEST", "PLAN_STALE", "PROCESSING_FAILED"} <= set(api_codes)
    assert {
        "INVALID_USAGE",
        "DOCUMENT_ACKNOWLEDGEMENT_REQUIRED",
        "IMAGE_PLAN_INVALID",
    } <= set(cli_codes)


def test_check_rejects_stale_contract(tmp_path: Path) -> None:
    path = tmp_path / "error-codes.json"
    MODULE.write_contract(path)
    MODULE.check_contract(path)
    payload = json.loads(path.read_text())
    payload["api_error_codes"].pop()
    path.write_text(json.dumps(payload))

    with pytest.raises(MODULE.ErrorCodeContractError, match="stale"):
        MODULE.check_contract(path)
