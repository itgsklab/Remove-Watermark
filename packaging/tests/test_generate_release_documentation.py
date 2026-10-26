from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "generate_release_documentation.py"
SPEC = importlib.util.spec_from_file_location("generate_release_documentation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def copy_contract_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    (root / "docs" / "release").mkdir(parents=True)
    (root / "backend").mkdir()
    shutil.copy(MODULE.SOURCE, root / "docs" / "release" / "release-status.json")
    shutil.copytree(MODULE.ROOT / "docs", root / "docs", dirs_exist_ok=True)
    shutil.copy(MODULE.ROOT / "backend" / "pyproject.toml", root / "backend" / "pyproject.toml")
    (root / "README.md").write_text("docs/release/RELEASE_STATUS.md\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text("docs/release/RELEASE_STATUS.md\n", encoding="utf-8")
    source = root / "docs" / "release" / "release-status.json"
    output = root / "docs" / "release" / "RELEASE_STATUS.md"
    return source, output


class ReleaseDocumentationTests(unittest.TestCase):
    def test_contract_renders_deterministically_and_covers_every_workflow(self) -> None:
        payload = MODULE.load_json(MODULE.SOURCE)
        MODULE.validate_contract(payload)
        self.assertEqual(MODULE.render(payload), MODULE.render(payload))
        self.assertEqual(payload["latest_stable"]["tag"], "v0.1.0")
        self.assertIs(payload["latest_stable"]["native_applications"], False)
        self.assertEqual(
            {row["id"] for row in payload["workflows"]},
            {
                "docx-vml",
                "docx-drawingml",
                "codecv-pdf",
                "general-pdf",
                "pdf-deep",
                "static-images",
                "xiaohongshu",
                "vlm-localization",
                "mask-refinement",
            },
        )

    def test_check_rejects_stale_generated_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, output = copy_contract_tree(Path(directory))
            MODULE.write_documentation(source, output)
            MODULE.check_documentation(source, output)
            output.write_text("stale\n", encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseDocumentationError, "stale"):
                MODULE.check_documentation(source, output)

    def test_contract_rejects_unknown_limitation_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, _ = copy_contract_tree(Path(directory))
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["limitations"][0]["applies_to"] = ["missing-workflow"]
            source.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseDocumentationError, "unknown workflow"):
                MODULE.validate_contract(MODULE.load_json(source), source.resolve().parents[2])

    def test_contract_rejects_native_application_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source, _ = copy_contract_tree(Path(directory))
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["latest_stable"]["native_applications"] = True
            source.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(MODULE.ReleaseDocumentationError, "Web-only"):
                MODULE.validate_contract(MODULE.load_json(source), source.resolve().parents[2])

    def test_github_release_metadata_must_match_public_contract(self) -> None:
        contract = MODULE.load_json(MODULE.SOURCE)
        stable = contract["latest_stable"]
        release = {
            "tagName": stable["tag"],
            "targetCommitish": stable["source_commit"],
            "publishedAt": stable["published_at"],
            "isDraft": False,
            "isPrerelease": False,
            "assets": [{"name": name} for name in reversed(stable["assets"])],
        }
        MODULE.validate_github_release(contract, release)
        release["assets"].pop()
        with self.assertRaisesRegex(MODULE.ReleaseDocumentationError, "assets differ"):
            MODULE.validate_github_release(contract, release)


if __name__ == "__main__":
    unittest.main()
