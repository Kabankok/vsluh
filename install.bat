@echo off
rem ASCII-shim: vsyu logiku delaet install.ps1 (UTF-8 BOM, russkie soobscheniya).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
