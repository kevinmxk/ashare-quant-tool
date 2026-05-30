@echo off
title A-Quant Tool
chcp 65001 >nul

set PROJECT_DIR=C:\Users\soap\.openclaw\workspace\ashare-quant-tool
set API_PORT=8018

:: cleanup zombie processes on target port
echo [1/4] Checking port %API_PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%API_PORT%"') do (
    echo [1/4] Found stale PID=%%a, killing...
    taskkill /F /PID %%a 2>nul && echo [1/4] Cleaned
)
timeout /t 2 /nobreak >nul

:: install frontend deps if needed
if not exist "%PROJECT_DIR%\frontend\node_modules" (
    echo [2/4] Installing frontend dependencies...
    cd /d "%PROJECT_DIR%\frontend"
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed
        pause
        exit /b 1
    )
    cd /d "%PROJECT_DIR%"
)

:: start backend (separate window)
echo [3/4] Starting FastAPI backend (port %API_PORT%)...
start "A-Quant-API" cmd /c "title A-Quant-API && cd /d "%PROJECT_DIR%" && chcp 65001 >nul && python -m uvicorn src.ashare_quant.api.main:app --host 0.0.0.0 --port %API_PORT% --reload"

:: wait for backend to come up
echo [3/4] Waiting for backend to start...
timeout /t 3 /nobreak >nul

:: start frontend (separate window)
echo [4/4] Starting Vue frontend (port 5173)...
start "A-Quant-Frontend" cmd /c "title A-Quant-Frontend && cd /d "%PROJECT_DIR%\frontend" && chcp 65001 >nul && npm run dev"

echo.
echo ========================================
echo  ALL STARTED!
echo  API:  http://localhost:%API_PORT%
echo  Web:  http://localhost:5173
echo  Docs: http://localhost:%API_PORT%/docs
echo ========================================

timeout /t 5
start http://localhost:5173