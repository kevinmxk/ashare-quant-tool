@echo off
title A-Quant Tool
chcp 936 >nul

set PROJECT_DIR=C:\Users\soap\.openclaw\workspace\ashare-quant-tool
set API_PORT=8004

if not exist "%PROJECT_DIR%\frontend\node_modules" (
    echo [Frontend] Installing dependencies...
    cd /d "%PROJECT_DIR%\frontend"
    call npm install
    if errorlevel 1 (
        echo [Frontend] npm install failed
        pause
        exit /b 1
    )
    cd /d "%PROJECT_DIR%"
)

echo [Backend] Starting FastAPI on port %API_PORT%...
start "A-Quant-API" cmd /k "cd /d "%PROJECT_DIR%" && uvicorn src.ashare_quant.api.main:app --port %API_PORT%"

echo [Frontend] Starting Vue on port 5173...
start "A-Quant-Frontend" cmd /k "cd /d "%PROJECT_DIR%\frontend" && npm run dev"

echo.
echo ========================================
echo   Started!
echo   API:  http://localhost:%API_PORT%
echo   Web:  http://localhost:5173
echo ========================================

timeout /t 5
start http://localhost:5173
