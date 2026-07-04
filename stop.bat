@echo off
rem Ostanovit «Vsluh» (dvizhok i trey).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | Where-Object { $_.CommandLine -like '*vsluh*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
