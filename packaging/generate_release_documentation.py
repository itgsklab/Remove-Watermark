from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "release" / "release-status.json"
OUTPUT = ROOT / "docs" / "release" / "RELEASE_STATUS.md"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ALLOWED_MATURITY = {
    "supported": "支持",
    "experimental": "实验性",
    "opt-in": "显式启用",
    "opt-in-experimental": "显式启用、实验性",
    "evaluation-only": "仅离线评测",
    "unavailable": "不可用",
}
EXPECTED_TOP_LEVEL = {
    "schema_version",
    "latest_stable",
    "development",
    "workflows",
    "limitations",
}
EXPECTED_ASSETS = (
    "SHA256SUMS",
    "release-manifest.json",
    "remove-watermark-web-{version}.tar.gz",
    "wmrm-{version}-py3-none-any.whl",
    "wmrm-{version}.tar.gz",
)


class ReleaseDocumentationError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseDocumentationError(f"cannot read release status: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseDocumentationError("release status must be a JSON object")
    return payload


def expect_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise ReleaseDocumentationError(
            f"{label} keys differ: expected {sorted(expected)}, got {sorted(value)}"
        )


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReleaseDocumentationError(f"{label} must be non-empty text")
    return value.strip()


def project_version(root: Path) -> str:
    content = (root / "backend" / "pyproject.toml").read_text(encoding="utf-8")
    project_match = re.search(r"(?ms)^\[project\]\s*$.*?(?=^\[|\Z)", content)
    if not project_match:
        raise ReleaseDocumentationError("backend pyproject has no project table")
    version_match = re.search(
        r'(?m)^version\s*=\s*"(?P<version>[^"\r\n]+)"\s*$', project_match.group()
    )
    if not version_match:
        raise ReleaseDocumentationError("backend project version is missing")
    return require_text(version_match["version"], "backend project version")


def validate_contract(payload: dict[str, Any], root: Path = ROOT) -> None:
    expect_keys(payload, EXPECTED_TOP_LEVEL, "release status")
    if payload["schema_version"] != 1:
        raise ReleaseDocumentationError("unsupported release status schema")

    stable = payload["latest_stable"]
    if not isinstance(stable, dict):
        raise ReleaseDocumentationError("latest_stable must be an object")
    expect_keys(
        stable,
        {
            "version",
            "tag",
            "source_commit",
            "published_at",
            "interface",
            "native_applications",
            "assets",
        },
        "latest_stable",
    )
    stable_version = require_text(stable["version"], "latest_stable.version")
    if not re.fullmatch(r"\d+\.\d+\.\d+", stable_version):
        raise ReleaseDocumentationError("latest stable version must be semantic x.y.z")
    if stable["tag"] != f"v{stable_version}":
        raise ReleaseDocumentationError("latest stable tag does not match its version")
    if not re.fullmatch(r"[0-9a-f]{40}", require_text(stable["source_commit"], "source commit")):
        raise ReleaseDocumentationError("source commit must be a full lowercase SHA-1")
    if stable["interface"] != "web" or stable["native_applications"] is not False:
        raise ReleaseDocumentationError("the published delivery contract must remain Web-only")
    expected_assets = [name.format(version=stable_version) for name in EXPECTED_ASSETS]
    if stable["assets"] != expected_assets:
        raise ReleaseDocumentationError("stable release asset list is incomplete or out of order")

    development = payload["development"]
    if not isinstance(development, dict):
        raise ReleaseDocumentationError("development must be an object")
    expect_keys(development, {"version", "channel", "changelog"}, "development")
    if development["version"] != project_version(root):
        raise ReleaseDocumentationError("development version differs from backend/pyproject.toml")
    if development["channel"] != "unreleased-main":
        raise ReleaseDocumentationError("development channel must identify unreleased main")
    if development["changelog"] != "CHANGELOG.md":
        raise ReleaseDocumentationError("development changelog must be CHANGELOG.md")

    workflows = payload["workflows"]
    if not isinstance(workflows, list) or not workflows:
        raise ReleaseDocumentationError("workflows must be a non-empty list")
    workflow_ids: set[str] = set()
    for index, row in enumerate(workflows):
        if not isinstance(row, dict):
            raise ReleaseDocumentationError(f"workflow {index} must be an object")
        expect_keys(
            row,
            {"id", "name", "stable", "main", "documentation", "summary"},
            f"workflow {index}",
        )
        workflow_id = require_text(row["id"], f"workflow {index}.id")
        if workflow_id in workflow_ids:
            raise ReleaseDocumentationError(f"duplicate workflow id: {workflow_id}")
        workflow_ids.add(workflow_id)
        require_text(row["name"], f"workflow {workflow_id}.name")
        require_text(row["summary"], f"workflow {workflow_id}.summary")
        for surface in ("stable", "main"):
            if row[surface] not in ALLOWED_MATURITY:
                raise ReleaseDocumentationError(
                    f"workflow {workflow_id}.{surface} has an invalid maturity"
                )
        documentation = Path(require_text(row["documentation"], "workflow documentation"))
        if documentation.is_absolute() or ".." in documentation.parts:
            raise ReleaseDocumentationError(f"unsafe documentation path: {documentation}")
        if not (root / documentation).is_file():
            raise ReleaseDocumentationError(f"missing workflow documentation: {documentation}")

    limitations = payload["limitations"]
    if not isinstance(limitations, list) or not limitations:
        raise ReleaseDocumentationError("limitations must be a non-empty list")
    limitation_ids: set[str] = set()
    referenced_workflows: set[str] = set()
    for index, row in enumerate(limitations):
        if not isinstance(row, dict):
            raise ReleaseDocumentationError(f"limitation {index} must be an object")
        expect_keys(row, {"id", "applies_to", "statement"}, f"limitation {index}")
        limitation_id = require_text(row["id"], f"limitation {index}.id")
        if limitation_id in limitation_ids:
            raise ReleaseDocumentationError(f"duplicate limitation id: {limitation_id}")
        limitation_ids.add(limitation_id)
        statement = require_text(row["statement"], f"limitation {limitation_id}.statement")
        if len(statement) < 20:
            raise ReleaseDocumentationError(f"limitation {limitation_id} is not actionable")
        applies_to = row["applies_to"]
        if not isinstance(applies_to, list) or not applies_to:
            raise ReleaseDocumentationError(f"limitation {limitation_id} has no scope")
        for workflow_id in applies_to:
            if workflow_id != "all" and workflow_id not in workflow_ids:
                raise ReleaseDocumentationError(
                    f"limitation {limitation_id} references unknown workflow {workflow_id}"
                )
            if workflow_id != "all":
                referenced_workflows.add(workflow_id)
    if workflow_ids - referenced_workflows:
        missing = sorted(workflow_ids - referenced_workflows)
        raise ReleaseDocumentationError(
            f"workflows without a specific limitation: {missing}"
        )


def validate_github_release(
    contract: dict[str, Any], release: dict[str, Any]
) -> None:
    stable = contract["latest_stable"]
    expected = {
        "tagName": stable["tag"],
        "targetCommitish": stable["source_commit"],
        "publishedAt": stable["published_at"],
        "isDraft": False,
        "isPrerelease": False,
    }
    for field, value in expected.items():
        if release.get(field) != value:
            raise ReleaseDocumentationError(
                f"GitHub Release {field} differs from the public status contract"
            )
    assets = release.get("assets")
    if not isinstance(assets, list) or any(not isinstance(row, dict) for row in assets):
        raise ReleaseDocumentationError("GitHub Release assets must be an object list")
    names = sorted(row.get("name") for row in assets)
    if names != sorted(stable["assets"]):
        raise ReleaseDocumentationError(
            "GitHub Release assets differ from the public status contract"
        )


def render(payload: dict[str, Any]) -> str:
    stable = payload["latest_stable"]
    development = payload["development"]
    lines = [
        (
            "<!-- Generated by packaging/generate_release_documentation.py; "
            "edit release-status.json. -->"
        ),
        "# Release status, support matrix and known limitations",
        "",
        "This page is the public source of truth for packaged-release claims. The latest stable",
        f"release is [`{stable['tag']}`](https://github.com/itgsklab/Remove-Watermark/releases/tag/{stable['tag']})",
        f"from commit `{stable['source_commit']}`. It was published at `{stable['published_at']}`.",
        "The delivery is a Vue Web interface served by a local Python/FastAPI process; it does not",
        "include native desktop applications.",
        "",
        (
            f"The current `main` package version is `{development['version']}`, "
            "but `main` also contains"
        ),
        (
            f"work under [{development['channel']}](/CHANGELOG.md). Entries in "
            "`[Unreleased]` are not part"
        ),
        "of the stable download unless a later release explicitly includes them.",
        "",
        "## Public assets",
        "",
        f"The `{stable['tag']}` GitHub Release contains exactly these five public files:",
        "",
    ]
    lines.extend(f"- `{name}`" for name in stable["assets"])
    lines.extend(
        [
            "",
            (
                "Packaging reports, private samples, local status files, model weights and "
                "raw user data"
            ),
            "are not release assets.",
            "",
            "## Support matrix",
            "",
            "| Workflow | Stable v0.1.0 | Current main | Scope | Detailed boundary |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["workflows"]:
        path = row["documentation"]
        label = Path(path).stem.replace("_", " ").title()
        lines.append(
            f"| {row['name']} | {ALLOWED_MATURITY[row['stable']]} | "
            f"{ALLOWED_MATURITY[row['main']]} | {row['summary']} | [{label}](/%s) |" % path
        )
    lines.extend(
        [
            "",
            "`supported` means the documented structure and guarded workflow are implemented and",
            (
                "covered by repository tests. It does not mean every producer, template or "
                "visual result"
            ),
            (
                "is compatible. `opt-in` capabilities require explicit local configuration. "
                "Experimental"
            ),
            (
                "and evaluation-only capabilities must not be presented as general "
                "compatibility claims."
            ),
            "",
            "## Known limitations",
            "",
        ]
    )
    workflow_names = {row["id"]: row["name"] for row in payload["workflows"]}
    for row in payload["limitations"]:
        scope = "全部工作流" if row["applies_to"] == ["all"] else "、".join(
            workflow_names[item] for item in row["applies_to"]
        )
        lines.append(f"- **{scope}：** {row['statement']}")
    lines.extend(
        [
            "",
            "## Claim rules",
            "",
            (
                "- Describe `main` additions as unreleased until a new immutable release "
                "contains them."
            ),
            "- Describe CodeCV support as experimental until provenance-cleared real exports from",
            "  multiple template versions pass the documented corpus gate.",
            "- Do not describe mask refinement as a Web feature until its human-timing and product",
            "  integration gates pass.",
            (
                "- Linux, macOS and Windows evidence validates package and CLI behavior; "
                "it does not imply"
            ),
            "  that three native desktop applications exist.",
            "- Any release note must link this page and the workflow-specific boundary document.",
            "",
            "To recheck the public GitHub metadata without committing network output, run:",
            "",
            "```bash",
            (
                "gh release view v0.1.0 "
                "--json tagName,targetCommitish,publishedAt,isDraft,isPrerelease,assets \\"
            ),
            "  > work/v0.1.0-release.json",
            "python3 packaging/generate_release_documentation.py --check \\",
            "  --github-release-json work/v0.1.0-release.json",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def check_public_links(root: Path = ROOT) -> None:
    required = "docs/release/RELEASE_STATUS.md"
    for path in (root / "README.md", root / "CHANGELOG.md"):
        if required not in path.read_text(encoding="utf-8"):
            raise ReleaseDocumentationError(f"{path.name} does not link the release status")


def write_documentation(source: Path = SOURCE, output: Path = OUTPUT) -> None:
    payload = load_json(source)
    validate_contract(payload, source.resolve().parents[2])
    output.write_text(render(payload), encoding="utf-8")


def check_documentation(source: Path = SOURCE, output: Path = OUTPUT) -> None:
    payload = load_json(source)
    root = source.resolve().parents[2]
    validate_contract(payload, root)
    expected = render(payload)
    try:
        actual = output.read_text(encoding="utf-8")
    except OSError as exc:
        raise ReleaseDocumentationError(f"cannot read generated release status: {exc}") from exc
    if actual != expected:
        raise ReleaseDocumentationError(
            "generated release documentation is stale; run "
            "python3 packaging/generate_release_documentation.py"
        )
    check_public_links(root)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and verify public release status docs.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--github-release-json",
        type=Path,
        help="Also verify public metadata captured by gh release view.",
    )
    args = parser.parse_args()
    try:
        if args.check:
            check_documentation()
            if args.github_release_json:
                validate_github_release(load_json(SOURCE), load_json(args.github_release_json))
            print("release documentation is current")
        else:
            write_documentation()
            print(f"wrote {OUTPUT.relative_to(ROOT)}")
    except ReleaseDocumentationError as exc:
        parser.exit(1, f"release documentation check failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
