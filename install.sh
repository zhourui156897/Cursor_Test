#!/bin/bash
# ============================================
# 第二大脑 - 一键安装脚本
# 在新 Mac 上执行此脚本即可完成所有安装
# 用法: bash install.sh
# ============================================

set -e

# --- 颜色定义 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step=0
total_steps=8

progress() {
    step=$((step + 1))
    echo ""
    echo -e "${BLUE}[$step/$total_steps]${NC} ${GREEN}$1${NC}"
    echo "────────────────────────────────────"
}

success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

warn() {
    echo -e "  ${YELLOW}!${NC} $1"
}

fail() {
    echo -e "  ${RED}✗ 错误: $1${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       第二大脑 - 一键安装程序        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# --- 检测项目目录 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/VERSION" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
else
    PROJECT_DIR="$HOME/dierdanao"
fi

# ============================================
# 1. 检测并安装 Homebrew
# ============================================
progress "检查 Homebrew"
if command -v brew &>/dev/null; then
    success "Homebrew 已安装"
else
    warn "Homebrew 未安装，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon 需要额外设置 PATH
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    fi
    success "Homebrew 安装完成"
fi

# ============================================
# 2. 安装 Python / Node / Git
# ============================================
progress "安装必备工具 (Python, Node.js, Git)"

if ! command -v python3 &>/dev/null || ! python3 -c "import sys; assert sys.version_info >= (3,11)" 2>/dev/null; then
    warn "正在安装 Python 3.12..."
    brew install python@3.12
    success "Python 安装完成"
else
    success "Python $(python3 --version | awk '{print $2}') 已就绪"
fi

if ! command -v node &>/dev/null; then
    warn "正在安装 Node.js..."
    brew install node
    success "Node.js 安装完成"
else
    success "Node.js $(node --version) 已就绪"
fi

if ! command -v git &>/dev/null; then
    brew install git
fi
success "Git 已就绪"

# 可选: ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    warn "ffmpeg 未安装（视频转文字需要），跳过。如需要请执行: brew install ffmpeg"
else
    success "ffmpeg 已就绪"
fi

# ============================================
# 3. 获取代码
# ============================================
progress "获取项目代码"

if [ -f "$PROJECT_DIR/VERSION" ]; then
    success "项目代码已存在: $PROJECT_DIR"
else
    warn "正在从 GitHub 克隆..."
    git clone https://github.com/zhourui156897/Cursor_Test.git "$PROJECT_DIR"
    success "代码克隆完成"
fi

cd "$PROJECT_DIR"

# ============================================
# 4. 复制配置文件
# ============================================
progress "创建配置文件"

if [ ! -f .env ]; then
    cp .env.example .env
    success "已创建 .env（可稍后按需修改）"
else
    success ".env 已存在，跳过"
fi

if [ ! -f backend/config/user_config.yaml ]; then
    cp backend/config/user_config.example.yaml backend/config/user_config.yaml
    success "已创建 user_config.yaml（可在「设置」页面配置 LLM）"
else
    success "user_config.yaml 已存在，跳过"
fi

# ============================================
# 5. 安装后端 Python 依赖
# ============================================
progress "安装后端依赖"

cd "$PROJECT_DIR/backend"

if [ ! -d .venv ]; then
    python3 -m venv .venv
    success "虚拟环境已创建"
else
    success "虚拟环境已存在"
fi

source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install -e . -q
success "后端依赖安装完成"

# ============================================
# 6. 安装前端依赖
# ============================================
progress "安装前端依赖"

cd "$PROJECT_DIR/frontend"

if [ -f package-lock.json ]; then
    npm ci --silent
else
    npm install --silent
fi
success "前端依赖安装完成"

# ============================================
# 7. 初始化数据库 + 数据目录
# ============================================
progress "初始化数据库"

cd "$PROJECT_DIR/backend"
source .venv/bin/activate

mkdir -p ~/.dierdanao/data
chmod -R u+rwx ~/.dierdanao/data

python scripts/init_db.py
success "数据库初始化完成"

# ============================================
# 8. 创建 Obsidian Vault (如不存在)
# ============================================
progress "检查 Obsidian Vault"

VAULT_PATH="$HOME/Documents/ObsidianVault"
if [ ! -d "$VAULT_PATH" ]; then
    mkdir -p "$VAULT_PATH"
    success "已创建 Obsidian Vault: $VAULT_PATH"
else
    success "Obsidian Vault 已存在: $VAULT_PATH"
fi

# ============================================
# 完成
# ============================================
cd "$PROJECT_DIR"
VERSION=$(cat VERSION 2>/dev/null || echo "unknown")

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         安装完成! v${VERSION}             ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  启动服务:  ${YELLOW}cd $PROJECT_DIR && bash start.sh${NC}"
echo -e "  停止服务:  ${YELLOW}cd $PROJECT_DIR && bash stop.sh${NC}"
echo -e "  更新版本:  ${YELLOW}cd $PROJECT_DIR && bash update.sh${NC}"
echo ""
echo -e "  ${BLUE}提示: 首次使用请在浏览器「设置」页面配置 LLM API Key${NC}"
echo ""
