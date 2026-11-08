@echo off
cd /d "%~dp0"
rem Find this computer's Steam screenshots for Avatar Legends.
set "SHOTS="
for /d %%U in ("C:\Program Files (x86)\Steam\userdata\*") do if exist "%%~U\760\remote\2424420\screenshots" set "SHOTS=%%~U\760\remote\2424420\screenshots"
if not defined SHOTS (
  echo No Avatar Legends screenshots were found in Steam. Take some with F12 in the game first.
  pause >nul
  exit /b 1
)
echo Testing Avatar Reader on your saved screenshots. Please wait.
"venv\Scripts\python.exe" avatar_reader.py --selftest "%SHOTS%"
echo Test finished. The results are saved in selftest.txt. Press any key to close.
pause >nul
