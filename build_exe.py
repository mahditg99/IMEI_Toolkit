"""Build a standalone IMEI Toolkit .exe with PyInstaller.

Usage:
    python build_exe.py

Output:
    dist\\imei-toolkit\\imei-toolkit.exe   (onedir, windowed)

On Windows the `protocol` package is picked up automatically via `--paths .`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "imei-toolkit"


def main() -> int:
    if not sys.platform.startswith("win"):
        print("build_exe.py targets Windows. On Linux/macOS use pyinstaller directly.")
        return 1
    if shutil.which("pyinstaller") is None:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                           check=True)
        except subprocess.CalledProcessError:
            print("pip install pyinstaller failed; install it manually and retry.")
            return 1

    dist = os.path.join(HERE, "dist")
    build = os.path.join(HERE, "build")
    for d in (dist, build):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", APP_NAME,
        "--paths", HERE,
        "--add-data", f"protocol;protocol",
        os.path.join(HERE, "main.py"),
    ]
    print("$", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=HERE)
    exe = os.path.join(dist, APP_NAME, f"{APP_NAME}.exe")
    if rc == 0 and os.path.isfile(exe):
        print(f"\nOK: {exe}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
