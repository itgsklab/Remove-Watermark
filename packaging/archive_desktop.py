from __future__ import annotations

import platform
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def main() -> int:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin":
        source = DIST / "Watermark Remover.app"
        output = DIST / f"watermark-remover-macos-{machine}.tar.gz"
    elif system == "Windows":
        source = DIST / "Watermark Remover"
        output = DIST / f"watermark-remover-windows-{machine}.zip"
    else:
        source = DIST / "Watermark Remover"
        output = DIST / f"watermark-remover-linux-{machine}.tar.gz"
    if not source.exists():
        raise SystemExit(f"Desktop bundle does not exist: {source}")
    output.unlink(missing_ok=True)
    if output.suffix == ".zip":
        shutil.make_archive(
            str(output.with_suffix("")),
            "zip",
            root_dir=source.parent,
            base_dir=source.name,
        )
    else:
        with tarfile.open(output, "w:gz", dereference=False) as archive:
            archive.add(source, arcname=source.name)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
