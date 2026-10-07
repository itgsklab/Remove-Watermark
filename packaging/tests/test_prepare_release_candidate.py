from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGING = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGING))
SCRIPT = PACKAGING / "prepare_release_candidate.py"
SPEC = importlib.util.spec_from_file_location("prepare_release_candidate", SCRIPT)
assert SPEC and SPEC.loader
candidate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = candidate
SPEC.loader.exec_module(candidate)


class ReleaseCandidateTests(unittest.TestCase):
    commit = "3" * 40

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.contract = candidate.evidence.load_contract()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_report(self, system: str) -> Path:
        path = self.root / "reports" / system / "release-readiness.json"
        path.parent.mkdir(parents=True)
        payload = {
            "schema_version": 1,
            "status": "passed",
            "verified_at": "2026-10-07T00:00:00+00:00",
            "source_commit": self.commit,
            "source_dirty": False,
            "contract": {
                "version": self.contract["contract_version"],
                "sha256": candidate.evidence.sha256(candidate.evidence.CLI_CONTRACT),
                "target_public_version": self.contract["target_public_version"],
            },
            "package": {
                "version": self.contract["development_version"],
                "wheel": f"wmrm-{self.contract['development_version']}-py3-none-any.whl",
                "wheel_sha256": system.lower().encode().hex().ljust(64, "0")[:64],
            },
            "runtime": {
                "system": system,
                "release": "test-release",
                "architecture": "test-architecture",
                "python": "3.12.10",
            },
            "verified": {
                "commands": sorted(self.contract["commands"]),
                "exit_codes": sorted(self.contract["exit_codes"].values()),
                "plan_schemas": self.contract["plan_schemas"],
            },
        }
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def write_summary(self, reports: list[Path]) -> Path:
        payload = candidate.evidence.aggregate_reports(
            reports,
            contract=self.contract,
            expected_commit=self.commit,
        )
        path = self.root / "release-readiness-summary.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def complete_reports(self) -> list[Path]:
        return [self.write_report(system) for system in candidate.evidence.REQUIRED_SYSTEMS]

    def test_validates_summary_against_raw_platform_reports(self) -> None:
        reports = self.complete_reports()
        summary = self.write_summary(reports)
        payload, discovered = candidate.validate_aggregate_summary(
            summary,
            [self.root / "reports"],
            expected_commit=self.commit,
        )
        self.assertEqual(payload["source_commit"], self.commit)
        self.assertEqual(discovered, [path.resolve() for path in reports])

    def test_rejects_tampered_aggregate_summary(self) -> None:
        reports = self.complete_reports()
        summary = self.write_summary(reports)
        payload = json.loads(summary.read_text())
        payload["platforms"]["Linux"]["evidence_sha256"] = "0" * 64
        summary.write_text(json.dumps(payload))
        with self.assertRaisesRegex(candidate.CandidateError, "platforms"):
            candidate.validate_aggregate_summary(
                summary,
                [self.root / "reports"],
                expected_commit=self.commit,
            )

    def test_builds_complete_python_and_npm_version_update(self) -> None:
        for source in candidate.VERSION_SOURCES:
            path = self.root / source.path
            path.parent.mkdir(parents=True, exist_ok=True)
            old = "0.1.0.dev0" if source.flavor == "python" else "0.1.0-dev"
            path.write_text("\n".join([old] * source.expected_count))
        updates = candidate.build_version_updates(
            self.root,
            current_python="0.1.0.dev0",
            target_python="0.1.0rc1",
            current_npm="0.1.0-dev",
            target_npm="0.1.0-rc.1",
        )
        self.assertEqual(set(updates), {source.path for source in candidate.VERSION_SOURCES})
        self.assertTrue(all("0.1.0.dev0" not in text for text in updates.values()))
        self.assertTrue(all("0.1.0-dev" not in text for text in updates.values()))

    def test_requires_increasing_release_candidate_number(self) -> None:
        contract = dict(self.contract, development_version="0.1.0rc2")
        with self.assertRaisesRegex(candidate.CandidateError, "must increase"):
            candidate.target_versions(contract, 2)


if __name__ == "__main__":
    unittest.main()
