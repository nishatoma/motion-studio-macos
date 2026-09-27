@echo off
setlocal
cd /d "%~dp0"
set "MOTION_STUDIO_OPEN_BROWSER=1"
set "MOTION_STUDIO_PYTHON="
set "MOTION_STUDIO_PYTHON_ARGS="
if exist ".venv\Scripts\python.exe" set "MOTION_STUDIO_PYTHON=.venv\Scripts\python.exe"
if not defined MOTION_STUDIO_PYTHON (
    py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11)" >nul 2>&1
    if not errorlevel 1 (
        set "MOTION_STUDIO_PYTHON=py"
        set "MOTION_STUDIO_PYTHON_ARGS=-3.11"
    )
)
if not defined MOTION_STUDIO_PYTHON (
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "MOTION_STUDIO_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined MOTION_STUDIO_PYTHON (
    echo Python 3.11 is needed to launch Motion Studio. Installing it with WinGet...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo WinGet is missing. Install Microsoft's App Installer and Python 3.11, then run this file again.
        pause
        exit /b 1
    )
    winget install --id Python.Python.3.11 --exact --source winget --silent --no-upgrade --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo Python installation did not complete. See the message above.
        pause
        exit /b 1
    )
    if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "MOTION_STUDIO_PYTHON=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)
if not defined MOTION_STUDIO_PYTHON (
    echo Reopen this window after Python installation finishes, then double-click start_windows.bat again.
    pause
    exit /b 1
)
echo Starting Motion Studio. Open http://127.0.0.1:8765 if the browser does not open automatically.
"%MOTION_STUDIO_PYTHON%" %MOTION_STUDIO_PYTHON_ARGS% app.py
if errorlevel 1 pause
