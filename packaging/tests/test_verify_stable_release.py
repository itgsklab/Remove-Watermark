from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "verify_stable_release.py"
SPEC = importlib.util.spec_from_file_location("verify_stable_release", SCRIPT)
assert SPEC and SPEC.loader
stable = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stable)


class StableReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(stable.DEFAULT_POLICY.read_text(encoding="utf-8"))
        self.feedback = {
            "schema_version": 1,
            "target_version": "0.1.0",
            "candidate_tag": "v0.1.0rc2",
            "reviewed_at": "2026-10-12T00:00:00+08:00",
            "sources": [
                {
                    "kind": "maintainer-acceptance",
                    "reference": "local acceptance record",
                    "collected_at": "2026-10-12T00:00:00+08:00",
                }
            ],
            "issues": [],
            "verification": {
                "clean_install": True,
                "browser_routes": ["/", "/settings"],
                "privacy_scan": True,
                "vlm_enabled_by_default": False,
                "vlm_automatic_download": False,
                "vlm_manual_review_required": True,
            },
            "approval": {
                "approved": True,
                "reviewer": "release maintainer",
                "approved_at": "2026-10-12T00:00:00+08:00",
            },
        }

    def test_committed_policy_is_valid(self) -> None:
        validated = stable.validate_policy(self.policy)
        self.assertEqual(validated["target_version"], "0.1.0")

    def test_rejects_tampered_release_asset_digest(self) -> None:
        policy = copy.deepcopy(self.policy)
        policy["required_release_candidates"][1]["assets"]["SHA256SUMS"] = "invalid"
        with self.assertRaisesRegex(stable.StableReleaseError, "SHA-256"):
            stable.validate_policy(policy)

    def test_complete_feedback_is_ready(self) -> None:
        result = stable.validate_feedback(self.feedback, stable.validate_policy(self.policy))
        self.assertEqual(result["status"], "ready")

    def test_acceptance_can_be_recorded_before_approval(self) -> None:
        feedback = copy.deepcopy(self.feedback)
        feedback["approval"] = {"approved": False, "reviewer": "", "approved_at": ""}
        result = stable.validate_feedback(
            feedback,
            stable.validate_policy(self.policy),
            require_approval=False,
        )
        self.assertEqual(result["status"], "acceptance-passed-approval-pending")

    def test_require_ready_rejects_pending_approval(self) -> None:
        feedback = copy.deepcopy(self.feedback)
        feedback["approval"] = {"approved": False, "reviewer": "", "approved_at": ""}
        with self.assertRaisesRegex(stable.StableReleaseError, "explicitly approved"):
            stable.validate_feedback(feedback, stable.validate_policy(self.policy))

    def test_rejects_missing_real_feedback_source(self) -> None:
        feedback = copy.deepcopy(self.feedback)
        feedback["sources"] = []
        with self.assertRaisesRegex(stable.StableReleaseError, "at least 1"):
            stable.validate_feedback(feedback, stable.validate_policy(self.policy))

    def test_rejects_unresolved_reproducible_high_issue(self) -> None:
        feedback = copy.deepcopy(self.feedback)
        feedback["issues"] = [
            {"id": "issue-1", "severity": "high", "reproducible": True, "status": "open"}
        ]
        with self.assertRaisesRegex(stable.StableReleaseError, "issue-1"):
            stable.validate_feedback(feedback, stable.validate_policy(self.policy))

    def test_rejects_vlm_enabled_by_default(self) -> None:
        feedback = copy.deepcopy(self.feedback)
        feedback["verification"]["vlm_enabled_by_default"] = True
        with self.assertRaisesRegex(stable.StableReleaseError, "VLM"):
            stable.validate_feedback(feedback, stable.validate_policy(self.policy))


if __name__ == "__main__":
    unittest.main()
