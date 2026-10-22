from __future__ import annotations

import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "audit_release_assets.py"
SPEC = importlib.util.spec_from_file_location("audit_release_assets", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


class ReleaseAssetAuditTests(unittest.TestCase):
    version = "0.2.0rc1"
    commit = "1" * 40

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.wheel_entries = {"wmrm/__init__.py": b'__version__ = "0.2.0rc1"\n'}
        self.sdist_entries = {f"wmrm-{self.version}/README.md": b"public source\n"}
        self.web_entries: dict[str, bytes] = {
            f"remove-watermark-web-{self.version}/frontend/index.html": b'<div id="app"></div>',
            f"remove-watermark-web-{self.version}/frontend/assets/app.js": b"console.log('ok')",
        }
        self.write_assets()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def zip_bytes(entries: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries.items():
                archive.writestr(name, payload)
        return output.getvalue()

    @staticmethod
    def tar_bytes(entries: dict[str, bytes]) -> bytes:
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, payload in entries.items():
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        return output.getvalue()

    def write_assets(self) -> None:
        wheel_name = f"wmrm-{self.version}-py3-none-any.whl"
        sdist_name = f"wmrm-{self.version}.tar.gz"
        web_name = f"remove-watermark-web-{self.version}.tar.gz"
        wheel = self.zip_bytes(self.wheel_entries)
        sdist = self.tar_bytes(self.sdist_entries)
        web_entries = dict(self.web_entries)
        web_entries[f"remove-watermark-web-{self.version}/packages/{wheel_name}"] = wheel
        web_entries[f"remove-watermark-web-{self.version}/packages/{sdist_name}"] = sdist
        artifacts = {wheel_name: wheel, sdist_name: sdist, web_name: self.tar_bytes(web_entries)}
        for name, payload in artifacts.items():
            (self.root / name).write_bytes(payload)
        checksums = "".join(
            f"{audit.sha256_bytes(artifacts[name])}  {name}\n" for name in sorted(artifacts)
        )
        (self.root / "SHA256SUMS").write_text(checksums, encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "version": self.version,
            "source": {"commit": self.commit},
            "artifacts": [
                {
                    "name": name,
                    "bytes": len(payload),
                    "sha256": audit.sha256_bytes(payload),
                }
                for name, payload in artifacts.items()
            ],
        }
        (self.root / "release-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    def run_audit(self) -> dict[str, object]:
        return audit.audit_release_assets(
            self.root,
            version=self.version,
            expected_commit=self.commit,
        )

    def test_accepts_complete_nested_release_asset_set(self) -> None:
        report = self.run_audit()
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["asset_count"], 5)
        self.assertGreaterEqual(report["archive_count"], 5)

    def test_rejects_private_files_local_paths_and_model_weights(self) -> None:
        failures = (
            ({"STATUS.md": b"private progress"}, "private file"),
            ({"wmrm/config.txt": b"/Users/alice/private/data"}, "macos-home-path"),
            ({"wmrm/model.safetensors": b"weights"}, "model weight"),
        )
        for extra, expected in failures:
            with self.subTest(expected=expected):
                self.wheel_entries = {
                    "wmrm/__init__.py": b'__version__ = "0.2.0rc1"\n',
                    **extra,
                }
                self.write_assets()
                with self.assertRaisesRegex(audit.AssetAuditError, expected):
                    self.run_audit()

    def test_rejects_checksum_tampering(self) -> None:
        wheel = self.root / f"wmrm-{self.version}-py3-none-any.whl"
        wheel.write_bytes(wheel.read_bytes() + b"tampered")
        with self.assertRaisesRegex(audit.AssetAuditError, "SHA256SUMS mismatch"):
            self.run_audit()

    def test_rejects_archive_path_traversal(self) -> None:
        self.sdist_entries = {f"wmrm-{self.version}/../private.txt": b"private"}
        self.write_assets()
        with self.assertRaisesRegex(audit.AssetAuditError, "unsafe path"):
            self.run_audit()

    def test_rejects_archive_links(self) -> None:
        sdist_name = f"wmrm-{self.version}.tar.gz"
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            member = tarfile.TarInfo(f"wmrm-{self.version}/private-link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/tmp/private"
            archive.addfile(member)
        (self.root / sdist_name).write_bytes(output.getvalue())
        artifacts = {
            name: (self.root / name).read_bytes()
            for name in audit.expected_asset_names(self.version)
            if name not in {"SHA256SUMS", "release-manifest.json"}
        }
        (self.root / "SHA256SUMS").write_text(
            "".join(
                f"{audit.sha256_bytes(artifacts[name])}  {name}\n"
                for name in sorted(artifacts)
            ),
            encoding="utf-8",
        )
        manifest = json.loads((self.root / "release-manifest.json").read_text())
        manifest["artifacts"] = [
            {
                "name": name,
                "bytes": len(payload),
                "sha256": audit.sha256_bytes(payload),
            }
            for name, payload in artifacts.items()
        ]
        (self.root / "release-manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(audit.AssetAuditError, "link or special file"):
            self.run_audit()

    def test_policy_pins_all_downloaded_asset_digests(self) -> None:
        report = self.run_audit()
        pinned = {item["name"]: item["sha256"] for item in report["assets"]}
        verified = audit.audit_release_assets(
            self.root,
            version=self.version,
            expected_policy_assets=pinned,
        )
        self.assertEqual(verified["status"], "passed")
        pinned["SHA256SUMS"] = "0" * 64
        with self.assertRaisesRegex(audit.AssetAuditError, "policy digest mismatch"):
            audit.audit_release_assets(
                self.root,
                version=self.version,
                expected_policy_assets=pinned,
            )


if __name__ == "__main__":
    unittest.main()
