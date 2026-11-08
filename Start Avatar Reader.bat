@echo off
setlocal
cd /d "%~dp0"
title Avatar Reader

if exist "venv\Scripts\pythonw.exe" goto run

echo Setting up Avatar Reader for the first time.
echo This downloads a few parts and takes a few minutes. Please wait.
echo.

set "PY="
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo Python was not found, so I am installing Python 3.12 now.
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

echo Creating the program environment.
%PY% -m venv venv
if errorlevel 1 goto fail

echo Installing parts. This is the slow step.
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto fail

rem Find this computer's Steam screenshots for the game (for the self test).
set "SHOTS="
for /d %%U in ("C:\Program Files (x86)\Steam\userdata\*") do if exist "%%~U\760\remote\2424420\screenshots" set "SHOTS=%%~U\760\remote\2424420\screenshots"
if exist "%SHOTS%" (
  echo Testing the reader on your saved screenshots.
  "venv\Scripts\python.exe" avatar_reader.py --selftest "%SHOTS%"
)
echo.
echo Setup finished.

:run
rem Close any copy that is already running, so only one reader speaks.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or Name='python.exe'\" | Where-Object { $_.CommandLine -like '*avatar_reader.py*' -and $_.CommandLine -notlike '*--selftest*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
echo Starting Avatar Reader. Press Control Shift Q at any time to quit it.
start "" "venv\Scripts\pythonw.exe" "%~dp0avatar_reader.py"
timeout /t 3 >nul
exit /b 0

:fail
echo.
echo Setup did not finish. The messages above say what went wrong.
if exist venv rmdir /s /q venv
echo Press any key to close this window.
pause >nul
exit /b 1
