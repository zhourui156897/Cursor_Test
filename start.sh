#!/bin/bash
# ============================================
# 第二大脑 - 一键启动
# 用法: bash start.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo ""
echo -e "${GREEN}第二大脑 v${VERSION} - 启动服务${NC}"
echo "────────────────────────────────────"

# 检查是否已在运行
if pgrep -f "uvicorn app.main:app" &>/dev/null; then
    warn_running=true
    echo -e "  ${YELLOW}! 后端似乎已在运行，将先停止旧进程${NC}"
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    sleep 1
fi
if pgrep -f "vite.*--port" &>/dev/null; then
    echo -e "  ${YELLOW}! 前端似乎已在运行，将先停止旧进程${NC}"
    pkill -f "vite.*--port" 2>/dev/null || true
    sleep 1
fi

# 创建日志目录
mkdir -p "$PROJECT_DIR/logs"

# 启动后端
echo -e "  ${BLUE}启动后端...${NC}"
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
    > "$PROJECT_DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo -e "  ${GREEN}✓${NC} 后端已启动 (PID: $BACKEND_PID)"

# 启动前端
echo -e "  ${BLUE}启动前端...${NC}"
cd "$PROJECT_DIR/frontend"
nohup npx vite --port 5173 --host \
    > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo -e "  ${GREEN}✓${NC} 前端已启动 (PID: $FRONTEND_PID)"

# 等待后端就绪
echo -e "  ${BLUE}等待服务就绪...${NC}"
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} 后端已就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e "  ${YELLOW}! 后端启动较慢，请稍后访问或查看日志: logs/backend.log${NC}"
    fi
    sleep 1
done

# 自动打开浏览器
sleep 2
open "http://localhost:5173" 2>/dev/null || true

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           服务已启动!                ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  前端地址:  ${YELLOW}http://localhost:5173${NC}"
echo -e "  后端文档:  ${YELLOW}http://localhost:8000/docs${NC}"
echo -e "  查看日志:  ${YELLOW}tail -f logs/backend.log${NC}"
echo -e "  停止服务:  ${YELLOW}bash stop.sh${NC}"
echo ""
