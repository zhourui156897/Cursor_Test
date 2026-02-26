#!/bin/bash
# ============================================
# 第二大脑 - 一键停止
# 用法: bash stop.sh
# ============================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${GREEN}第二大脑 - 停止服务${NC}"
echo "────────────────────────────────────"

stopped=0

if pgrep -f "uvicorn app.main:app" &>/dev/null; then
    pkill -f "uvicorn app.main:app"
    echo -e "  ${GREEN}✓${NC} 后端已停止"
    stopped=$((stopped + 1))
else
    echo -e "  ${YELLOW}-${NC} 后端未运行"
fi

if pgrep -f "vite" &>/dev/null; then
    pkill -f "vite"
    echo -e "  ${GREEN}✓${NC} 前端已停止"
    stopped=$((stopped + 1))
else
    echo -e "  ${YELLOW}-${NC} 前端未运行"
fi

echo ""
if [ $stopped -gt 0 ]; then
    echo -e "  ${GREEN}所有服务已停止${NC}"
else
    echo -e "  ${YELLOW}没有正在运行的服务${NC}"
fi
echo ""
