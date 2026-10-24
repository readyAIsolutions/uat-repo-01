@echo off
REM MARLIN one-click launcher (Windows). Put a shortcut to this file on the
REM Desktop named "MARLIN" with a MARLIN icon. Double-click -> everything starts.
setlocal
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo Docker Desktop is not installed or not on PATH. Install Docker Desktop, then retry.
  pause & exit /b 1
)

echo Starting Docker Desktop if needed...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
timeout /t 8 >nul

echo Starting MARLIN containers...
docker compose up -d --build
if errorlevel 1 ( echo MARLIN failed to start. & pause & exit /b 1 )

echo Waiting for MARLIN to become healthy...
set /a tries=0
:wait
set /a tries+=1
curl -s -o nul http://localhost:8011/health && goto ready
if %tries% GEQ 30 ( echo MARLIN did not become healthy in time. & pause & exit /b 1 )
timeout /t 2 >nul
goto wait

:ready
echo MARLIN is up. Opening http://localhost:8011/
start "" http://localhost:8011/
endlocal
