from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "verify_workflow_action_pins.py"
SPEC = importlib.util.spec_from_file_location("verify_workflow_action_pins", SCRIPT)
assert SPEC and SPEC.loader
workflow_pins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow_pins)


def test_accepts_full_commit_sha_and_local_action(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        "steps:\n"
        "  - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
        "  - uses: ./local-action\n",
        encoding="utf-8",
    )

    failures, action_count = workflow_pins.find_unpinned_actions(tmp_path)

    assert failures == []
    assert action_count == 1


def test_rejects_moving_action_reference(tmp_path: Path) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yaml").write_text(
        "steps:\n  - uses: actions/checkout@v7\n",
        encoding="utf-8",
    )

    failures, action_count = workflow_pins.find_unpinned_actions(tmp_path)

    assert failures == [".github/workflows/ci.yaml:2: actions/checkout@v7"]
    assert action_count == 1
