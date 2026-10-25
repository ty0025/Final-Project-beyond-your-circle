@echo off
rem One-shot start for Windows: create .venv if missing, install requirements, run the app.
rem Usage: start.bat [--host HOST] [--port PORT] [--no-browser]
setlocal
cd /d "%~dp0"
set "VERSION_OK=import sys; sys.exit(sys.version_info < (3, 10))"

rem Reuse .venv only if it runs Python 3.10+ and has pip; otherwise a venv left by an old
rem Python or a failed first attempt would make every later run fail the same way.
if not exist ".venv" goto create
if not exist ".venv\Scripts\python.exe" goto recreate
".venv\Scripts\python.exe" -c "%VERSION_OK%" >nul 2>nul
if errorlevel 1 goto recreate
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 goto recreate
goto install

:recreate
echo [setup] The existing .venv is broken or uses Python older than 3.10; recreating it ...
rmdir /s /q .venv
if exist ".venv" (
    echo [setup] Could not delete the .venv folder. Close programs using it, delete it by hand and try again.
    goto fail
)

:create
echo [setup] Creating virtual environment in .venv ...
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 -c "%VERSION_OK%" >nul 2>nul
if errorlevel 1 goto use_python
py -3 -m venv .venv
goto check_venv
:use_python
python -c "%VERSION_OK%" >nul 2>nul
if errorlevel 1 goto no_python
python -m venv .venv
:check_venv
if not exist ".venv\Scripts\python.exe" goto venv_failed
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 goto venv_failed
goto install

:no_python
echo [setup] Python 3.10 or newer is required. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and try again.
goto fail

:venv_failed
if exist ".venv" rmdir /s /q .venv
echo [setup] Could not create .venv. Install Python 3.10 or newer from https://www.python.org/downloads/ and try again.
goto fail

:install
echo [setup] Installing requirements ...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [setup] pip install failed. Check your internet connection, or delete the .venv folder and try again.
    goto fail
)
".venv\Scripts\python.exe" run.py %*
if errorlevel 1 goto fail
exit /b 0

:fail
rem Keep the window open when started by double-click so the message can be read.
pause
exit /b 1
