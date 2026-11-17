@echo off
rem ATSC road evaluator for Windows. First run creates demo\.venv and installs the packages.
setlocal
chcp 65001 >nul
set "HERE=%~dp0"
set "VENV=%HERE%.venv"
if exist "%VENV%\.ready" goto run
echo First run: setting up a Python environment (takes a minute)...
if exist "%VENV%" rmdir /s /q "%VENV%"
where py >nul 2>nul
if %errorlevel%==0 (py -3 -m venv "%VENV%") else (python -m venv "%VENV%")
if not exist "%VENV%\Scripts\python.exe" goto nopython
"%VENV%\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 goto nopython
"%VENV%\Scripts\python.exe" -m pip install -q --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -q -r "%HERE%requirements.txt"
if errorlevel 1 (echo Package install failed. Check your internet connection and try again. & pause & exit /b 1)
echo ok> "%VENV%\.ready"
:run
"%VENV%\Scripts\python.exe" "%HERE%atsc_cmd.py"
exit /b 0
:nopython
echo Python 3.11 or newer is required: https://www.python.org/downloads/  (tick "Add python.exe to PATH")
pause
exit /b 1
