@echo off
setlocal
cd /d "%~dp0"

echo.
echo ========================================
echo   Vibara Agentic Workbench
echo ========================================
echo.
echo Starting Backend and Frontend...
echo.

if not exist "backend\.env" (
  echo ERROR: backend\.env not found.
  echo Copy backend\.env.example to backend\.env and add your API keys.
  pause
  exit /b 1
)

if not exist "backend\venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment not found.
  echo Create it with: python -m venv backend\venv
  echo Then install dependencies with: backend\venv\Scripts\python -m pip install -r backend\requirements.txt
  pause
  exit /b 1
)

if not exist "frontend\node_modules" (
  echo ERROR: frontend dependencies not installed.
  echo Run: cd frontend ^&^& npm install
  pause
  exit /b 1
)

echo [1/2] Starting Backend...
start "Vibara Backend" cmd /k "cd /d "%~dp0backend" ^&^& venv\Scripts\python.exe main.py"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Frontend...
start "Vibara Frontend" cmd /k "cd /d "%~dp0frontend" ^&^& npm run dev"

echo.
echo ========================================
echo   Vibara is starting!
echo ========================================
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
pause
