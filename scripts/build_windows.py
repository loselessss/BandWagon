"""Build in a dedicated, version-checked Windows environment."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise SystemExit("This build requires Windows x64.")
    if platform.python_version() != "3.14.6":
        raise SystemExit("Install CPython 3.14.6 x64, then run this script with that interpreter.")
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)
    os.environ["PYTHONNOUSERSITE"] = "1"
    environment = ROOT / ".venv-build"
    python = environment / "Scripts" / "python.exe"
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(environment)
    actual = subprocess.check_output([str(python), "-I", "-c", "import platform; print(platform.python_version())"], text=True).strip()
    if actual != "3.14.6":
        raise SystemExit(".venv-build uses another Python version; move it aside and retry.")
    run(str(python), "-I", "-m", "pip", "install", "--isolated", "--only-binary=:all:", "-r", str(ROOT / "requirements-build.lock"))
    normalize = lambda name: name.lower().replace("_", "-").replace(".", "-")
    expected = {}
    for line in (ROOT / "requirements-build.lock").read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            expected[normalize(name)] = version
    installed = json.loads(subprocess.check_output([str(python), "-I", "-m", "pip", "list", "--format=json"], text=True))
    actual = {normalize(p["name"]): p["version"] for p in installed if p["name"].lower() != "pip"}
    if actual != expected:
        raise SystemExit(".venv-build contains unexpected packages or versions; move it aside and retry.")
    run(str(python), "-I", "-m", "pip", "check")
    run(str(python), "-I", "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noconsole",
        "--name", "BandWagon", "--icon", "bandwagon.ico", "--add-data", "bandwagon.ico;.",
        "--add-data", "bandwagon_composite.ico;.", "--manifest", "bandwagon.manifest",
        "--splash", "bandwagon_splash.png", "--collect-submodules", "bandwagon",
        "--collect-all", "scipy", "--collect-all", "cv2", "--exclude-module", "tkinter", "run.py")
    print("Build succeeded: dist/BandWagon/BandWagon.exe")


if __name__ == "__main__":
    main()
