@echo off
rem Zapusk «Vsluh»: dvizhok + trey (dva processa, pythonw = bez konsoli).
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Snachala zapustite install.bat
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -X utf8 -m vsluh
start "" ".venv\Scripts\pythonw.exe" -X utf8 -m vsluh.traymain
