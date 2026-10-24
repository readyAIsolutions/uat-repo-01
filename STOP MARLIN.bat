@echo off
setlocal
cd /d "%~dp0"
echo [MARLIN] Stopping MARLIN containers...
docker compose down
echo [MARLIN] Stopped.
pause
endlocal
