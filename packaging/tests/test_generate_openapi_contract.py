from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "generate_openapi_contract.py"
SPEC = importlib.util.spec_from_file_location("generate_openapi_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_contract_is_deterministic_and_versioned() -> None:
    first = MODULE.build_contract()
    second = MODULE.build_contract()

    assert first == second
    assert first["openapi"] == "3.1.0"
    assert first["info"]["version"] == "0.1.0"
    assert len(first["paths"]) == 22
    assert all(path.startswith("/api/v1/") for path in first["paths"])
    assert "/api/v1/image-suggestions/vlm" in first["paths"]
    assert not any("timing" in path for path in first["paths"])


def test_check_rejects_stale_contract(tmp_path: Path) -> None:
    path = tmp_path / "openapi.json"
    MODULE.write_contract(path)
    MODULE.check_contract(path)
    payload = json.loads(path.read_text())
    payload["paths"].pop("/api/v1/health")
    path.write_text(json.dumps(payload))

    with pytest.raises(MODULE.OpenApiContractError, match="stale"):
        MODULE.check_contract(path)
