#!/usr/bin/env bash
# ===================================================
#  Build BandWagon.app with PyInstaller (macOS only)
# ===================================================
# Must be run ON a Mac — PyInstaller is not a cross-compiler, so this
# cannot be run from Windows/Linux to produce a Mac app (and vice versa).
#
# First time only:  python3 -m pip install pyinstaller
# Run this from the same folder as run.py.
#
# Notes:
#  --onedir + --windowed: on macOS this produces a proper BandWagon.app
#    bundle (double-clickable, no terminal window) inside dist/.
#  No --splash here: PyInstaller's native splash screen is NOT supported
#    on macOS (it relies on a Tcl/Tk thread that macOS's GUI toolkit
#    disallows) — the app just opens straight to the main window instead.
#    The code already handles this gracefully (the splash-close call is
#    wrapped in try/except), so nothing else needs to change.
#  --collect-all scipy / cv2: bundles everything those need for analysis
#    (find_peaks) and warp (cv2). Makes the build bigger but avoids
#    missing-module errors.
#  Want an app icon? Add --icon=path/to/icon.icns (macOS needs .icns,
#    not .ico — there isn't one in this repo yet).
#
# We call PyInstaller as `python3 -m PyInstaller` (not the bare
# "pyinstaller" command) on purpose: if you have more than one Python
# install (e.g. Homebrew vs system Python), the bare command can point
# to a different one than "python3", or simply not be on PATH at all
# even though the package is installed.

set -e

if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 was not found on PATH."
    echo "        Install it from https://python.org or via 'brew install python'."
    exit 1
fi

if ! python3 -m PyInstaller --version >/dev/null 2>&1; then
    echo "[ERROR] PyInstaller is not installed for \"python3\"."
    echo "        Run this once, then try again:"
    echo
    echo "            python3 -m pip install pyinstaller"
    echo
    exit 1
fi

python3 -m PyInstaller --noconfirm --clean --onedir --windowed \
    --name BandWagon \
    --collect-submodules bandwagon \
    --collect-all scipy \
    --collect-all cv2 \
    run.py

echo
echo "============================================"
echo " Build finished - check dist/BandWagon.app"
echo "============================================"
