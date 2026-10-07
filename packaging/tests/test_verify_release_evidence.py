from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "verify_release_evidence.py"
SPEC = importlib.util.spec_from_file_location("verify_release_evidence", SCRIPT)
assert SPEC and SPEC.loader
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


class ReleaseEvidenceTests(unittest.TestCase):
    commit = "1" * 40

    def setUp(self) -> None:
        self.contract = evidence.load_contract()
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_report(self, system: str, *, commit: str | None = None, dirty: bool = False) -> Path:
        path = self.root / system / "release-readiness.json"
        path.parent.mkdir(exist_ok=True)
        payload = {
            "schema_version": 1,
            "status": "passed",
            "verified_at": "2026-10-07T00:00:00+00:00",
            "source_commit": commit or self.commit,
            "source_dirty": dirty,
            "contract": {
                "version": self.contract["contract_version"],
                "sha256": evidence.sha256(evidence.CLI_CONTRACT),
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

    def complete_reports(self) -> list[Path]:
        return [self.write_report(system) for system in evidence.REQUIRED_SYSTEMS]

    def test_accepts_one_matching_report_per_required_platform(self) -> None:
        aggregate = evidence.aggregate_reports(
            self.complete_reports(),
            contract=self.contract,
            expected_commit=self.commit,
        )
        self.assertEqual(aggregate["status"], "passed")
        self.assertEqual(set(aggregate["platforms"]), set(evidence.REQUIRED_SYSTEMS))

    def test_rejects_missing_platform(self) -> None:
        with self.assertRaisesRegex(evidence.EvidenceError, "Missing required platform"):
            evidence.aggregate_reports(
                [self.write_report("Darwin"), self.write_report("Linux")],
                contract=self.contract,
                expected_commit=self.commit,
            )

    def test_rejects_mixed_commits(self) -> None:
        reports = self.complete_reports()
        reports[-1] = self.write_report("Windows", commit="2" * 40)
        with self.assertRaisesRegex(evidence.EvidenceError, "expected"):
            evidence.aggregate_reports(
                reports,
                contract=self.contract,
                expected_commit=self.commit,
            )

    def test_rejects_dirty_source(self) -> None:
        reports = self.complete_reports()
        reports[0] = self.write_report("Darwin", dirty=True)
        with self.assertRaisesRegex(evidence.EvidenceError, "dirty source tree"):
            evidence.aggregate_reports(
                reports,
                contract=self.contract,
                expected_commit=self.commit,
            )


if __name__ == "__main__":
    unittest.main()
