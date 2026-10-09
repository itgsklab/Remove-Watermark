from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGING = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGING / "generate_release_metadata.py"
SPEC = importlib.util.spec_from_file_location("generate_release_metadata", SCRIPT)
assert SPEC and SPEC.loader
metadata = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = metadata
SPEC.loader.exec_module(metadata)


class ReleaseMetadataTests(unittest.TestCase):
    def test_canonical_text_bytes_normalizes_platform_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            lf.write_bytes(b"first\nsecond\n")
            crlf.write_bytes(b"first\r\nsecond\r\n")
            self.assertEqual(
                metadata.canonical_text_bytes(lf),
                metadata.canonical_text_bytes(crlf),
            )

    def test_vendored_florence_runtime_is_declared(self) -> None:
        components = metadata.vendored_components()

        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].license, "Apache-2.0")
        self.assertEqual(components[0].usage, "optional runtime source")


if __name__ == "__main__":
    unittest.main()
