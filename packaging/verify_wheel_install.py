from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
CONSTRAINTS = ROOT / "packaging" / "constraints.txt"


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def venv_python(directory: Path) -> Path:
    if os.name == "nt":
        return directory / "Scripts" / "python.exe"
    return directory / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the backend wheel and verify it in a new virtual environment."
    )
    parser.add_argument(
        "--keep-work",
        type=Path,
        help="Keep intermediate wheel and virtual environment files in this directory.",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 12):
        raise SystemExit("Python 3.12 or newer is required")

    temporary = None
    if args.keep_work:
        work = args.keep_work.resolve()
        work.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="wmrm-wheel-check-")
        work = Path(temporary.name)

    wheels = work / "wheels"
    environment = work / "venv"
    wheels.mkdir(parents=True, exist_ok=True)
    run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(wheels), "."],
        cwd=BACKEND,
    )
    built = sorted(wheels.glob("wmrm-*.whl"))
    if len(built) != 1:
        raise SystemExit(f"Expected one wmrm wheel, found {len(built)}")

    venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    python = venv_python(environment)
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--constraint",
            str(CONSTRAINTS),
            str(built[0]),
        ],
        cwd=work,
        env=clean_env,
    )
    run([str(python), "-m", "pip", "check"], cwd=work, env=clean_env)
    probe = (
        "import importlib.metadata as m; "
        "from wmrm.api.app import create_app; "
        "app=create_app(); "
        "assert app.title == 'Watermark Remover'; "
        "assert m.version('wmrm') == '0.1.0.dev0'; "
        "print('wheel import probe: ok')"
    )
    run([str(python), "-I", "-c", probe], cwd=work, env=clean_env)
    print(f"clean wheel installation verified: {built[0].name}")
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
