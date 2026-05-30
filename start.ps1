# A-Share Quant Tool 启动脚本 (PowerShell)
# 用法: .\start.ps1

$projectRoot = "C:\Users\soap\.openclaw\workspace\ashare-quant-tool"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "A-Share Quant Tool 启动器" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "启动后端 (FastAPI) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot'; uvicorn src.ashare_quant.api.main:app --port 8018"

Write-Host "启动前端 (Vue 3) ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$projectRoot\frontend'; npm install; npm run dev"

Write-Host ""
Write-Host "两个终端窗口已打开。" -ForegroundColor Cyan
Write-Host "后端地址: http://localhost:8018" -ForegroundColor Yellow
Write-Host "前端地址: http://localhost:5173" -ForegroundColor Yellow
