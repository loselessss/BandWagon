@echo off
setlocal
REM ===================================================
REM  Build the BandWagon installer (Setup.exe)
REM ===================================================
REM Order:
REM   1) Run build_exe.bat first -> creates dist\BandWagon\ (onedir build)
REM   2) Run this file (build_installer.bat)
REM First time only: install Inno Setup (free) from
REM   https://jrsoftware.org/isdl.php

if not exist "dist\BandWagon\BandWagon.exe" (
  echo [ERROR] dist\BandWagon\BandWagon.exe not found.
  echo         Run build_exe.bat first to create it.
  pause
  exit /b 1
)

set ISCC=
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe

if "%ISCC%"=="" (
  echo [ERROR] Could not find Inno Setup (ISCC.exe).
  echo         Install Inno Setup 6 from https://jrsoftware.org/isdl.php
  echo         then run this file again.
  pause
  exit /b 1
)

"%ISCC%" installer.iss

echo.
echo ============================================
echo  Build finished - check Output\BandWagon_Setup_*.exe
echo ============================================
pause
