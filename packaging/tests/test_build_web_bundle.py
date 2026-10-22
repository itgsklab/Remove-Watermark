from __future__ import annotations

import hashlib
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "build_web_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_web_bundle", SCRIPT)
assert SPEC and SPEC.loader
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)

VERIFY_SCRIPT = Path(__file__).resolve().parents[1] / "verify_web_bundle.py"
VERIFY_SPEC = importlib.util.spec_from_file_location("verify_web_bundle", VERIFY_SCRIPT)
assert VERIFY_SPEC and VERIFY_SPEC.loader
verify = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(verify)


class WebBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.frontend = self.root / "frontend"
        (self.frontend / "assets").mkdir(parents=True)
        (self.frontend / "index.html").write_text("<main>wmrm</main>")
        (self.frontend / "assets" / "app.js").write_text("console.log('wmrm')")
        self.wheel = self.root / "wmrm-0.1.0rc1-py3-none-any.whl"
        self.sdist = self.root / "wmrm-0.1.0rc1.tar.gz"
        self.license = self.root / "LICENSE"
        self.wheel.write_bytes(b"wheel")
        self.sdist.write_bytes(b"sdist")
        self.license.write_bytes(b"license")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_build_is_reproducible_and_complete(self) -> None:
        payloads = bundle.bundle_payloads(
            version="0.1.0rc1",
            wheel=self.wheel,
            sdist=self.sdist,
            frontend_dir=self.frontend,
            license_path=self.license,
        )
        first = self.root / "first.tar.gz"
        second = self.root / "second.tar.gz"
        for output in (first, second):
            bundle.write_bundle(
                output,
                version="0.1.0rc1",
                payloads=payloads,
                source_date_epoch=1_700_000_000,
            )
        self.assertEqual(
            hashlib.sha256(first.read_bytes()).digest(),
            hashlib.sha256(second.read_bytes()).digest(),
        )

        with tarfile.open(first, "r:gz") as archive:
            names = archive.getnames()
            prefix = "remove-watermark-web-0.1.0rc1"
            self.assertIn(f"{prefix}/frontend/index.html", names)
            self.assertIn(f"{prefix}/frontend/assets/app.js", names)
            self.assertIn(f"{prefix}/packages/{self.wheel.name}", names)
            self.assertIn(f"{prefix}/packages/{self.sdist.name}", names)
            checksums = archive.extractfile(f"{prefix}/SHA256SUMS")
            assert checksums is not None
            checksum_text = checksums.read().decode()
            self.assertIn(f"packages/{self.wheel.name}", checksum_text)
            for member in archive.getmembers():
                self.assertEqual(member.mtime, 1_700_000_000)
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.gid, 0)

        report = verify.verify_bundle(
            first,
            version="0.1.0rc1",
            expected_sha256=hashlib.sha256(first.read_bytes()).hexdigest(),
            source_date_epoch=1_700_000_000,
        )
        self.assertTrue(report["verified"])
        self.assertEqual(report["payload_file_count"], 6)

        extracted = self.root / "extracted"
        extracted_root = verify.extract_verified_bundle(
            first, extracted, version="0.1.0rc1"
        )
        self.assertEqual(
            (extracted_root / "frontend" / "index.html").read_text(),
            "<main>wmrm</main>",
        )

    def test_verifier_rejects_tampering_and_digest_mismatch(self) -> None:
        payloads = bundle.bundle_payloads(
            version="0.1.0rc1",
            wheel=self.wheel,
            sdist=self.sdist,
            frontend_dir=self.frontend,
            license_path=self.license,
        )
        payloads[verify.PurePosixPath("frontend/index.html")] = b"tampered"
        output = self.root / "tampered.tar.gz"
        bundle.write_bundle(
            output,
            version="0.1.0rc1",
            payloads=payloads,
            source_date_epoch=1_700_000_000,
        )
        with self.assertRaisesRegex(verify.BundleVerificationError, "SHA-256 mismatch"):
            verify.verify_bundle(output, version="0.1.0rc1")
        with self.assertRaisesRegex(verify.BundleVerificationError, "bundle SHA-256 mismatch"):
            verify.verify_bundle(
                output,
                version="0.1.0rc1",
                expected_sha256="0" * 64,
            )

    def test_verifier_rejects_symbolic_links_and_unsafe_paths(self) -> None:
        for name, member_name in (
            ("link.tar.gz", "remove-watermark-web-0.1.0rc1/link"),
            ("escape.tar.gz", "remove-watermark-web-0.1.0rc1/../escape"),
        ):
            output = self.root / name
            with tarfile.open(output, "w:gz") as archive:
                if name.startswith("link"):
                    member = tarfile.TarInfo(member_name)
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/tmp/target"
                else:
                    member = tarfile.TarInfo(member_name)
                    member.size = 1
                member.mode = 0o644
                member.uid = member.gid = 0
                member.uname = member.gname = "root"
                archive.addfile(member, None if member.issym() else io.BytesIO(b"x"))
            expected = (
                "unsupported archive member type"
                if name.startswith("link")
                else "unsafe archive path"
            )
            with self.assertRaisesRegex(verify.BundleVerificationError, expected):
                verify.verify_bundle(output, version="0.1.0rc1")

    def test_rejects_incomplete_frontend_and_wrong_artifact_names(self) -> None:
        with self.assertRaisesRegex(bundle.BundleError, "Incomplete Vue"):
            bundle.bundle_payloads(
                version="0.1.0rc1",
                wheel=self.wheel,
                sdist=self.sdist,
                frontend_dir=self.root / "missing",
                license_path=self.license,
            )
        with self.assertRaisesRegex(bundle.BundleError, "wheel filename"):
            bundle.bundle_payloads(
                version="0.1.0rc1",
                wheel=self.root / "wrong.whl",
                sdist=self.sdist,
                frontend_dir=self.frontend,
                license_path=self.license,
            )


if __name__ == "__main__":
    unittest.main()
