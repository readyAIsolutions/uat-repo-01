@echo off
setlocal
cd /d "%~dp0"
echo ===== MARLIN DIAGNOSTICS =====
echo.
echo [1] Docker installed?
where docker || echo   NOT FOUND - install Docker Desktop
echo.
echo [2] Docker running?
docker info >nul 2>nul && echo   RUNNING || echo   NOT RUNNING - start Docker Desktop
echo.
echo [3] Containers:
docker compose ps
echo.
echo [4] MARLIN health (/health):
curl -s http://localhost:8011/health || echo   NOT RESPONDING
echo.
echo [5] Rhino.Compute status (/api/rhino/status):
curl -s http://localhost:8011/api/rhino/status || echo   NOT RESPONDING
echo.
echo [6] Rhino.Compute reachable directly (from Windows host)?
curl -s http://localhost:6500/healthcheck || echo   NOT REACHABLE - is Rhino.Compute running?
echo.
echo [7] Last 40 MARLIN log lines:
docker compose logs --tail=40 marlin-api
echo.
echo ===== END DIAGNOSTICS =====
pause
endlocal
