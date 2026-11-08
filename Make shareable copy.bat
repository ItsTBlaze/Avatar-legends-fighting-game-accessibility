@echo off
setlocal
cd /d "%~dp0"
title Make a shareable copy of Avatar Reader

if not exist "venv\Scripts\python.exe" (
  echo Please open Start Avatar Reader once first, so the parts are installed.
  echo Press any key to close this window.
  pause >nul
  exit /b 1
)

echo Building a shareable copy of Avatar Reader.
echo This takes a few minutes. Please wait until it says Done.
echo.

echo Step 1 of 4: getting the packaging tool.
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q pyinstaller > build_log.txt 2>&1
if errorlevel 1 goto fail

echo Step 2 of 4: packaging the program. This is the slow step.
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name "Avatar Reader" --add-data "lib;lib" --collect-all winrt --hidden-import comtypes.client avatar_reader.py >> build_log.txt 2>&1
if errorlevel 1 goto fail
copy /y "share\README.txt" "dist\Avatar Reader\README.txt" >nul
copy /y "share\LICENSES.txt" "dist\Avatar Reader\LICENSES.txt" >nul
if exist LICENSE copy /y LICENSE "dist\Avatar Reader\LICENSE.txt" >nul

echo Step 3 of 4: testing the packaged program on your screenshots.
rem Find this computer's Steam screenshots for the game (for the self test).
set "SHOTS="
for /d %%U in ("C:\Program Files (x86)\Steam\userdata\*") do if exist "%%~U\760\remote\2424420\screenshots" set "SHOTS=%%~U\760\remote\2424420\screenshots"
if exist "%SHOTS%" (
  start "" /wait "dist\Avatar Reader\Avatar Reader.exe" --selftest "%SHOTS%"
  if exist "dist\Avatar Reader\selftest.txt" move /y "dist\Avatar Reader\selftest.txt" "packaged_selftest.txt" >nul
  if exist "dist\Avatar Reader\avatar_reader.log" del "dist\Avatar Reader\avatar_reader.log"
)

echo Step 4 of 4: making the zip file.
if exist "Avatar Reader.zip" del "Avatar Reader.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Avatar Reader' -DestinationPath 'Avatar Reader.zip' -Force" >> build_log.txt 2>&1
if errorlevel 1 goto fail

echo.
echo Done. The file to share is Avatar Reader.zip, in this folder.
echo Press any key to close this window.
pause >nul
exit /b 0

:fail
echo.
echo Something went wrong. The details are in build_log.txt in this folder.
echo Press any key to close this window.
pause >nul
exit /b 1
