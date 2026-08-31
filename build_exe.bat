@echo off
rem Builds the standalone IMEI Toolkit .exe (requires Python + pip).
cd /d "%~dp0"
"C:\Program Files\Python312\python.exe" build_exe.py
echo.
pause
