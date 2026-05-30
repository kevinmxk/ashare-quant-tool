@echo off
chcp 65001 >nul
title A-Quant Stop

set PID_FILE=%TEMP%\aquant_api.pid

if exist "%PID_FILE%" (
    set /p PID=<"%PID_FILE%"
    if defined PID (
        echo [stop] Found backend PID %PID%, sending SIGTERM...
        taskkill /F /PID %PID% 2>nul
        echo [stop] Backend stopped.
    ) else (
        echo [stop] PID file is empty, falling back to port scan.
        goto :SCAN_PORT
    )
) else (
    echo [stop] No PID file found, falling back to port scan.
    goto :SCAN_PORT
)

del "%PID_FILE%" 2>nul

echo [stop] Also cleaning up stale processes on port 8018...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8018"') do (
    taskkill /F /PID %%a 2>nul
)

echo [stop] Done.
goto :END

:SCAN_PORT
echo [stop] Scanning port 8018 for leftover processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8018"') do (
    taskkill /F /PID %%a 2>nul && echo [stop] Killed PID %%a
)

echo [stop] Done.
goto :END

:END
echo.
pause