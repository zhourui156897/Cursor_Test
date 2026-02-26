#!/bin/bash
# ============================================
# 第二大脑 - 一键更新
# 用法: bash update.sh
# ============================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

OLD_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo ""
echo -e "${GREEN}第二大脑 - 一键更新${NC}"
echo -e "  当前版本: v${OLD_VERSION}"
echo "────────────────────────────────────"

# 1. 拉取最新代码
echo -e "  ${BLUE}拉取最新代码...${NC}"
git pull origin main
NEW_VERSION=$(cat VERSION 2>/dev/null || echo "unknown")
echo -e "  ${GREEN}✓${NC} 代码已更新 (v${OLD_VERSION} -> v${NEW_VERSION})"

# 2. 更新后端依赖
echo -e "  ${BLUE}更新后端依赖...${NC}"
cd "$PROJECT_DIR/backend"
source .venv/bin/activate
pip install -r requirements.txt -q
pip install -e . -q
echo -e "  ${GREEN}✓${NC} 后端依赖已更新"

# 3. 更新前端依赖
echo -e "  ${BLUE}更新前端依赖...${NC}"
cd "$PROJECT_DIR/frontend"
if [ -f package-lock.json ]; then
    npm ci --silent
else
    npm install --silent
fi
echo -e "  ${GREEN}✓${NC} 前端依赖已更新"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       更新完成! v${NEW_VERSION}               ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${YELLOW}请重启服务使更新生效:${NC}"
echo -e "    bash stop.sh && bash start.sh"
echo ""
