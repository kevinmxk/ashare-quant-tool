#!/usr/bin/env bash
# A-Share Quant Tool 启动脚本 (Bash)
# 用法: ./start.sh

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "========================================"
echo "A-Share Quant Tool 启动器"
echo "========================================"
echo ""

# 终端1：启动后端
echo "启动后端 (FastAPI) ..."
cd "$PROJECT_ROOT" || exit 1
uvicorn src.ashare_quant.api.main:app --reload --port 8000 &
BACKEND_PID=$!

# 终端2：启动前端
echo "启动前端 (Vue 3) ..."
cd "$PROJECT_ROOT/frontend" || exit 1
npm install
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "后端地址: http://localhost:8000"
echo "前端地址: http://localhost:5173"
echo "========================================"
echo "按 Enter 停止所有服务 ..."
read -r

kill "$BACKEND_PID" 2>/dev/null
kill "$FRONTEND_PID" 2>/dev/null
