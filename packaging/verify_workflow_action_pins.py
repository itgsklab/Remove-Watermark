from __future__ import annotations

import re
from pathlib import Path

ACTION_REF = re.compile(r"^[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*-\s+uses:\s*(?P<value>[^#\s]+)")


def find_unpinned_actions(root: Path) -> tuple[list[str], int]:
    workflow_dir = root / ".github" / "workflows"
    failures: list[str] = []
    action_count = 0

    workflows = sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")))
    for workflow in workflows:
        for line_number, line in enumerate(workflow.read_text(encoding="utf-8").splitlines(), 1):
            match = USES_LINE.match(line)
            if match is None:
                continue
            value = match.group("value")
            if value.startswith(("./", "docker://")):
                continue
            action_count += 1
            _, separator, reference = value.rpartition("@")
            if not separator or ACTION_REF.fullmatch(reference) is None:
                failures.append(f"{workflow.relative_to(root)}:{line_number}: {value}")

    return failures, action_count


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures, action_count = find_unpinned_actions(root)
    if failures:
        print("GitHub Actions must use immutable 40-character commit SHAs:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"Verified {action_count} immutable GitHub Action references.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
