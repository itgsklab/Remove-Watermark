from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "backend" / "pyproject.toml"
PYTHON_LOCK = ROOT / "packaging" / "constraints.txt"
NPM_MANIFEST = ROOT / "frontend" / "package.json"
NPM_LOCK = ROOT / "frontend" / "package-lock.json"
DEFAULT_INVENTORY = ROOT / "docs" / "THIRD_PARTY_DEPENDENCIES.md"
DEFAULT_SBOM = ROOT / "docs" / "release" / "sbom.spdx.json"

PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^;\s]+)(?:\s*;\s*(?P<marker>.+))?$"
)
NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)")


@dataclass(frozen=True, order=True)
class Component:
    ecosystem: str
    name: str
    version: str
    usage: str
    direct: bool
    condition: str = ""

    @property
    def key(self) -> str:
        return f"{self.ecosystem}:{self.name.lower()}@{self.version}:{self.usage}"

    @property
    def spdx_id(self) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9.-]+", "-", self.name).strip("-")
        suffix = hashlib.sha256(self.key.encode()).hexdigest()[:10]
        return f"SPDXRef-Package-{self.ecosystem}-{safe_name}-{suffix}"

    @property
    def purl(self) -> str:
        if self.ecosystem == "Python":
            return f"pkg:pypi/{quote(self.name, safe='')}@{quote(self.version, safe='')}"
        if self.name.startswith("@") and "/" in self.name:
            scope, package = self.name.split("/", 1)
            encoded_name = f"{quote(scope, safe='')}/{quote(package, safe='')}"
        else:
            encoded_name = quote(self.name, safe="")
        return f"pkg:npm/{encoded_name}@{quote(self.version, safe='')}"


def normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def requirement_name(value: str) -> str:
    match = NAME_RE.match(value)
    if not match:
        raise ValueError(f"Unable to read dependency name: {value!r}")
    return normalized_name(match.group(1))


def python_components() -> list[Component]:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    runtime = {requirement_name(item) for item in project.get("dependencies", [])}
    build = {
        requirement_name(item)
        for item in project.get("optional-dependencies", {}).get("packaging", [])
    }
    components: list[Component] = []
    for raw_line in PYTHON_LOCK.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN_RE.fullmatch(line)
        if not match:
            raise ValueError(f"Every Python release dependency must be exactly pinned: {line}")
        name = match.group("name")
        normalized = normalized_name(name)
        if normalized in runtime:
            usage = "runtime"
            direct = True
        elif normalized in build:
            usage = "build"
            direct = True
        else:
            usage = "locked transitive"
            direct = False
        components.append(
            Component(
                ecosystem="Python",
                name=name,
                version=match.group("version"),
                usage=usage,
                direct=direct,
                condition=(match.group("marker") or "").strip(),
            )
        )
    return components


def npm_components() -> list[Component]:
    manifest = json.loads(NPM_MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(NPM_LOCK.read_text(encoding="utf-8"))
    direct_names = set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))
    components: dict[str, Component] = {}
    for path, metadata in lock.get("packages", {}).items():
        if not path or "node_modules/" not in path or not metadata.get("version"):
            continue
        name = metadata.get("name") or path.rsplit("node_modules/", 1)[-1]
        if metadata.get("dev"):
            usage = "development"
        elif metadata.get("optional"):
            usage = "optional runtime"
        else:
            usage = "runtime"
        conditions: list[str] = []
        if metadata.get("os"):
            conditions.append("os=" + ",".join(metadata["os"]))
        if metadata.get("cpu"):
            conditions.append("cpu=" + ",".join(metadata["cpu"]))
        component = Component(
            ecosystem="npm",
            name=name,
            version=str(metadata["version"]),
            usage=usage,
            direct=name in direct_names,
            condition="; ".join(conditions),
        )
        components[component.key] = component
    return list(components.values())


def input_digest() -> str:
    digest = hashlib.sha256()
    for path in (PYPROJECT, PYTHON_LOCK, NPM_MANIFEST, NPM_LOCK):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(canonical_text_bytes(path))
        digest.update(b"\0")
    return digest.hexdigest()


def canonical_text_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def creation_time(existing_sbom: Path) -> str:
    if existing_sbom.exists():
        try:
            existing = json.loads(existing_sbom.read_text(encoding="utf-8"))
            value = existing["creationInfo"]["created"]
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
    if value := os.environ.get("SOURCE_DATE_EPOCH"):
        timestamp = int(value)
    else:
        timestamp = int(datetime.now(UTC).timestamp())
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def all_components() -> list[Component]:
    return sorted(python_components() + npm_components())


def render_inventory(components: list[Component], digest: str) -> str:
    python_count = sum(item.ecosystem == "Python" for item in components)
    npm_count = sum(item.ecosystem == "npm" for item in components)
    lines = [
        "# Third-party dependency inventory",
        "",
        "This file is generated from the pinned Python packaging constraints and npm lockfile.",
        "It records release inputs; it is not a legal opinion or a substitute for license review.",
        "Regenerate it with `make release-metadata` and verify it with `make release-metadata-check`.",
        "",
        f"- Input digest: `{digest}`",
        f"- Python packages: {python_count}",
        f"- npm packages: {npm_count}",
        "- License fields: `NOASSERTION` until an authoritative package-by-package review is recorded",
        "",
        "| Ecosystem | Package | Version | Usage | Direct | Platform condition |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in components:
        condition = item.condition.replace("|", "\\|") if item.condition else "—"
        lines.append(
            f"| {item.ecosystem} | `{item.name}` | `{item.version}` | {item.usage} | "
            f"{'yes' if item.direct else 'no'} | {condition} |"
        )
    return "\n".join(lines) + "\n"


def render_sbom(components: list[Component], digest: str, created: str) -> str:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    root_id = "SPDXRef-Package-Remove-Watermark"
    packages = [
        {
            "SPDXID": root_id,
            "name": "Remove Watermark",
            "versionInfo": project["version"],
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "AGPL-3.0-only",
            "licenseDeclared": "AGPL-3.0-only",
            "copyrightText": "Copyright 2026 Remove Watermark contributors",
            "primaryPackagePurpose": "APPLICATION",
        }
    ]
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        }
    ]
    for item in components:
        packages.append(
            {
                "SPDXID": item.spdx_id,
                "name": item.name,
                "versionInfo": item.version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "primaryPackagePurpose": "LIBRARY",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": item.purl,
                    }
                ],
                "comment": (
                    f"Ecosystem: {item.ecosystem}; usage: {item.usage}; "
                    f"direct: {'yes' if item.direct else 'no'}"
                    + (f"; condition: {item.condition}" if item.condition else "")
                ),
            }
        )
        relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": item.spdx_id,
            }
        )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Remove Watermark release-input SBOM",
        "documentNamespace": f"https://github.com/itgsklab/Remove-Watermark/sbom/{digest}",
        "creationInfo": {
            "created": created,
            "creators": ["Tool: Remove-Watermark-release-metadata/1.0"],
        },
        "documentDescribes": [root_id],
        "packages": packages,
        "relationships": relationships,
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_or_check(path: Path, content: str, *, check: bool) -> None:
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"Release metadata is stale: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic release metadata.")
    parser.add_argument("--check", action="store_true", help="Fail when committed outputs are stale.")
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--sbom", type=Path, default=DEFAULT_SBOM)
    args = parser.parse_args()
    components = all_components()
    digest = input_digest()
    write_or_check(args.inventory, render_inventory(components, digest), check=args.check)
    write_or_check(
        args.sbom,
        render_sbom(components, digest, creation_time(args.sbom)),
        check=args.check,
    )
    print(f"release metadata {'verified' if args.check else 'generated'}: {len(components)} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
