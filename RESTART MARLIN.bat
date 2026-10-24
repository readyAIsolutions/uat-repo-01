@echo off
setlocal
cd /d "%~dp0"
echo [MARLIN] Restarting MARLIN...
docker compose restart
echo [MARLIN] Restarted. Opening UI...
start "" http://localhost:8011/
endlocal
