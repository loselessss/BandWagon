@echo off
setlocal
cd /d "%~dp0"
REM Requires CPython 3.14.6 x64. Dependencies live in .venv-build.
py -3.14 --version >nul 2>&1
if errorlevel 1 (
  python scripts\build_windows.py
) else (
  py -3.14 scripts\build_windows.py
)
set BUILD_RESULT=%ERRORLEVEL%
if not "%BUILD_RESULT%"=="0" echo [ERROR] Build failed. See the output above.
pause
exit /b %BUILD_RESULT%
