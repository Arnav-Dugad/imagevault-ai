"""Build the ImageVault desktop app into dist/.

    python packaging/build.py

It builds the website (npm) and then bundles Python, the server and the
website into one program with PyInstaller. On Windows the result is
dist/ImageVault.exe.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*command: str, cwd: Path = ROOT) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, shell=sys.platform == "win32" and command[0] == "npm")


def main() -> None:
    run("npm", "ci", cwd=ROOT / "frontend")
    run("npm", "run", "build", cwd=ROOT / "frontend")

    separator = ";" if sys.platform == "win32" else ":"
    run(
        sys.executable, "-m", "PyInstaller", str(ROOT / "packaging" / "launcher.py"),
        "--name", "ImageVault",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(ROOT / "packaging" / "icon.ico"),
        "--add-data", f"{ROOT / 'app' / 'static'}{separator}app/static",
        "--collect-submodules", "uvicorn",
        "--distpath", "dist",
        "--workpath", "build",
        "--specpath", "build",
    )
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    print("\nDone! Your app is in", ROOT / "dist")


if __name__ == "__main__":
    main()
