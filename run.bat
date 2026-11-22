@echo off
REM GeoMind - one-command local dev launcher (Windows port of run.sh).
REM Starts the FastAPI gateway (:8000) and the Vite web app (:5173) together.
REM Stop with Ctrl+C - it reaches every child in this console.

setlocal
cd /d "%~dp0"

REM Conda env: GEOMIND_CONDA_ENV overrides, then CONDA_ENV, else "geo" (this machine's env).
if defined GEOMIND_CONDA_ENV (set "CONDA_ENV=%GEOMIND_CONDA_ENV%") else if not defined CONDA_ENV set "CONDA_ENV=geo"

where conda >nul 2>nul || (echo conda not found. Install Miniforge/conda first. 1>&2 & exit /b 1)
where pnpm.cmd >nul 2>nul || (echo pnpm.cmd not found. Install pnpm first ^(npm i -g pnpm^). 1>&2 & exit /b 1)
where curl >nul 2>nul || (echo curl not found. Windows 10+ ships it in System32; check PATH. 1>&2 & exit /b 1)

if not exist "apps\web\node_modules" (
  echo [GeoMind] installing web deps...
  pushd apps\web
  call pnpm.cmd install
  set "RC=%errorlevel%"
  popd
  if not "%RC%"=="0" exit /b %RC%
)

echo [GeoMind] starting gateway on http://localhost:8000 ...
start "GeoMind gateway" /b cmd /c "conda run --no-capture-output -n %CONDA_ENV% uvicorn geofront_api.main:app --host 0.0.0.0 --port 8000"

set /a TRIES=0
:wait_gateway
curl -sf http://localhost:8000/api/v1/health >nul 2>nul && goto gateway_ready
set /a TRIES+=1
if %TRIES% geq 30 (
  echo [GeoMind] gateway did not become healthy after 30s. 1>&2
  exit /b 1
)
ping -n 2 127.0.0.1 >nul
goto wait_gateway
:gateway_ready
echo [GeoMind] gateway ready.

echo [GeoMind] starting web on http://localhost:5173 ...
start "GeoMind web" /b cmd /c "cd /d apps\web && call pnpm.cmd dev"

REM Ctrl+C in this console signals uvicorn and vite too; nothing to clean up here.
:wait_loop
ping -n 5 127.0.0.1 >nul
goto wait_loop
