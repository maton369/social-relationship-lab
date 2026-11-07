@echo off
setlocal DisableDelayedExpansion
if defined TD_EXE goto found
for /d %%D in ("%ProgramFiles%\Derivative\TouchDesigner*") do if exist "%%~D\bin\TouchDesigner.exe" set "TD_EXE=%%~D\bin\TouchDesigner.exe"
:found
if not defined TD_EXE (
  echo ERROR: Install TouchDesigner 2025 with Python 3.11 first.
  echo Or set TD_EXE to the full path of TouchDesigner.exe.
  exit /b 1
)
if not exist "%TD_EXE%" (
  echo ERROR: TD_EXE does not exist: "%TD_EXE%"
  exit /b 1
)
if not exist "%~dp0Social_Relationship_Lab_v3.toe" (
  echo ERROR: Place this script next to Social_Relationship_Lab_v3.toe.
  exit /b 1
)
start "" "%TD_EXE%" "%~dp0Social_Relationship_Lab_v3.toe"
exit /b %errorlevel%
