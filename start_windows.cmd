@echo off
setlocal DisableDelayedExpansion
rem Use TouchDesigner's bundled Python. No separate Python install is required.
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
for %%F in ("%TD_EXE%") do set "TD_PYTHON=%%~dpFpython.exe"
if not exist "%TD_PYTHON%" (
  echo ERROR: TouchDesigner's bundled python.exe was not found.
  exit /b 1
)
"%TD_PYTHON%" -I "%~dp0windows_launcher.py" --td "%TD_EXE%" %*
exit /b %errorlevel%
