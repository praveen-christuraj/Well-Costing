@echo off
title Drilling Costing – Dev

echo Running database migrations ...
cd /d %~dp0backend
call .venv\Scripts\activate.bat
python -m alembic upgrade head
if errorlevel 1 (
  echo ERROR: Migration failed. Check your DATABASE_URL in backend\.env
  pause
  exit /b 1
)

echo Starting backend (FastAPI) ...
start "Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting frontend (Nuxt) ...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers are starting.
echo   Backend  ^>  http://127.0.0.1:8000
echo   Frontend ^>  http://localhost:3000
echo.
echo Close the individual terminal windows to stop each server.
pause
