@echo off
title A-Quant Tool Manager
chcp 65001 >nul

:MENU
cls
echo ========================================
echo    A-Quant Tool Manager
echo ========================================
echo.
echo    [1] Start - Launch backend + frontend
echo    [2] Stop + Exit  - Kill backend and close
echo.
set /p CHOICE="Select (1/2): "

if "%CHOICE%"=="1" (
    call "%~dp0start_quant_tool.bat"
    echo.
    echo Press any key to return to menu...
    pause >nul
    goto MENU
)

if "%CHOICE%"=="2" (
    call "%~dp0stop.bat"
    exit /b
)

echo Invalid option, try again.
timeout /t 2 /nobreak >nul
goto MENU