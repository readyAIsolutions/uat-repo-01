@echo off
setlocal
cd /d "%~dp0"
REM START MARLIN — ensures Docker Desktop, starts containers, waits, opens the UI.
where docker >nul 2>nul || (echo [MARLIN] Docker Desktop is not installed. Install it from docker.com and retry. & pause & exit /b 1)
echo [MARLIN] Ensuring Docker Desktop is running...
docker info >nul 2>nul || (
  start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  echo [MARLIN] Waiting for Docker to start...
  :dockerwait
  timeout /t 5 >nul
  docker info >nul 2>nul || goto dockerwait
)
echo [MARLIN] Starting MARLIN containers...
docker compose up -d --build || (echo [MARLIN] Failed to start containers. Run "MARLIN DIAGNOSTICS.bat". & pause & exit /b 1)
echo [MARLIN] Waiting for health check...
set /a tries=0
:wait
set /a tries+=1
curl -s -o nul http://localhost:8011/health && goto ready
if %tries% GEQ 30 (echo [MARLIN] Timed out waiting for health. Run "MARLIN DIAGNOSTICS.bat". & pause & exit /b 1)
timeout /t 2 >nul
goto wait
:ready
echo [MARLIN] Ready. Opening http://localhost:8011/
start "" http://localhost:8011/
endlocal
