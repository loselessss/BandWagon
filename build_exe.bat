@echo off
setlocal
REM ===================================================
REM  Build BandWagon.exe with PyInstaller
REM ===================================================
REM First time only:  pip install pyinstaller
REM Run this file from the same folder as run.py and
REM bandwagon_splash.png.
REM
REM Notes:
REM  --onedir : produces a folder (dist\BandWagon\) instead of a
REM    single exe. Slower to distribute (whole folder) but starts
REM    much faster (no self-extraction on every launch). Switch to
REM    --onefile if you want a single portable .exe instead (slower
REM    startup, but only one file to hand out without an installer).
REM  --splash bandwagon_splash.png : native PyInstaller splash,
REM    shows instantly before Python/Qt even loads.
REM  --collect-all scipy / cv2 : bundles everything those need
REM    for analysis (find_peaks) and warp (cv2). Makes the build
REM    bigger but avoids missing-module errors.
REM
REM To change the splash image, just replace bandwagon_splash.png
REM with another file of the same size.
REM
REM We call PyInstaller as  <python> -m PyInstaller  (not the bare
REM "pyinstaller" command) on purpose: if you have more than one
REM Python install, the bare command can point to a different one,
REM or simply not be on PATH at all even though the package is
REM installed. We try both "python" and the "py" launcher below,
REM since on many Windows setups only one of the two is on PATH.

set PYCMD=
python --version >nul 2>&1
if not errorlevel 1 set PYCMD=python
if "%PYCMD%"=="" (
  py --version >nul 2>&1
  if not errorlevel 1 set PYCMD=py
)
if "%PYCMD%"=="" (
  echo [ERROR] Neither "python" nor "py" was found on PATH.
  echo         Install Python from https://python.org and make sure
  echo         "Add python.exe to PATH" is checked during setup.
  pause
  exit /b 1
)

%PYCMD% -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] PyInstaller is not installed for "%PYCMD%".
  echo         Run this once, then try again:
  echo.
  echo             %PYCMD% -m pip install pyinstaller
  echo.
  pause
  exit /b 1
)

%PYCMD% -m PyInstaller --noconfirm --clean --onedir --noconsole --name BandWagon --splash "bandwagon_splash.png" --collect-submodules bandwagon --collect-all scipy --collect-all cv2 run.py

echo.
echo ============================================
echo  Build finished - check dist\BandWagon\BandWagon.exe
echo ============================================
pause
