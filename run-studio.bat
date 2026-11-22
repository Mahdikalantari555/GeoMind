@echo off
REM GeoMind studio - one-command local dev launcher (Windows port of run-studio.sh).
REM Starts the FastAPI gateway (:8000) and the studio Vite app (:5174) together.
REM Stop with Ctrl+C - it reaches every child in this console.
REM (bash twin exits when either process dies; here Ctrl+C is the stop mechanism.)

setlocal
cd /d "%~dp0"

for %%c in (conda pnpm.cmd curl) do (
  where %%c >nul 2>nul || (echo Missing %%c. Install it and follow README.md Quickstart before launching. 1>&2 & exit /b 1)
)

if defined GEOMIND_CONDA_ENV (set "CONDA_ENV=%GEOMIND_CONDA_ENV%") else set "CONDA_ENV=geo"

start "GeoMind gateway" /b cmd /c "conda run --no-capture-output -n %CONDA_ENV% uvicorn geofront_api.main:app --port 8000"

set /a TRIES=0
:wait_gateway
curl -fsS --max-time 2 http://127.0.0.1:8000/api/v1/health >nul 2>nul && goto gateway_ready
set /a TRIES+=1
if %TRIES% geq 60 (
  echo Gateway did not become healthy on port 8000 1>&2
  exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_gateway
:gateway_ready

echo [GeoMind] starting studio on http://localhost:5174 ...
start "GeoMind studio" /b cmd /c "cd /d apps\studio && call pnpm.cmd dev --port 5174 --strictPort"

:wait_loop
ping -n 5 127.0.0.1 >nul
goto wait_loop
