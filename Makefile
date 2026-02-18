.PHONY: setup start stop dev logs health check-deps reset-db backup restore

# 首次安装：检查依赖 + 安装 + 初始化数据库 + 启动全部
setup: check-deps
	@echo "=== 安装 Python 依赖 ==="
	cd backend && pip install -e ".[dev]"
	@echo "=== 安装前端依赖 ==="
	cd frontend && npm install
	@echo "=== 初始化数据库 ==="
	cd backend && python scripts/init_db.py
	@echo "=== 复制配置文件（如不存在）==="
	@test -f .env || cp .env.example .env
	@test -f backend/config/user_config.yaml || cp backend/config/user_config.example.yaml backend/config/user_config.yaml
	@echo "=== 安装完成！运行 make start 启动服务 ==="

# 检查前置依赖
check-deps:
	@echo "=== 检查前置依赖 ==="
	@command -v python3 >/dev/null 2>&1 || { echo "需要 Python 3.11+"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "需要 Node.js 18+"; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "需要 Docker Desktop"; exit 1; }
	@echo "依赖检查通过"

# 启动所有服务
start:
	@echo "=== 启动 Docker 服务 ==="
	docker compose up -d
	@echo "=== 启动后端 ==="
	cd backend && nohup python -m uvicorn app.main:app --host 0.0.0.0 --port $${BACKEND_PORT:-8000} --reload > ../logs/backend.log 2>&1 &
	@echo "=== 启动前端 ==="
	cd frontend && nohup npm run dev -- --port $${FRONTEND_PORT:-3000} > ../logs/frontend.log 2>&1 &
	@echo "=== 全部启动完成 ==="
	@echo "前端: http://localhost:$${FRONTEND_PORT:-3000}"
	@echo "后端: http://localhost:$${BACKEND_PORT:-8000}/docs"
	@echo "Neo4j: http://localhost:$${NEO4J_HTTP_PORT:-7474}"

# 停止所有服务
stop:
	@echo "=== 停止服务 ==="
	-pkill -f "uvicorn app.main:app" 2>/dev/null
	-pkill -f "vite" 2>/dev/null
	docker compose down
	@echo "=== 全部停止 ==="

# 开发模式（前台运行，热重载）
dev:
	@echo "=== 启动 Docker 服务 ==="
	docker compose up -d
	@echo "=== 后端开发模式 ==="
	cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port $${BACKEND_PORT:-8000} --reload

# 查看日志
logs:
	@mkdir -p logs
	@echo "=== 后端日志 ==="
	@tail -50 logs/backend.log 2>/dev/null || echo "无后端日志"
	@echo "\n=== Docker 日志 ==="
	docker compose logs --tail=20

# 健康检查
health:
	@echo "=== 服务状态 ==="
	@curl -sf http://localhost:$${BACKEND_PORT:-8000}/health && echo " 后端: OK" || echo " 后端: DOWN"
	@curl -sf http://localhost:$${FRONTEND_PORT:-3000} > /dev/null && echo " 前端: OK" || echo " 前端: DOWN"
	@docker compose ps --format "table {{.Name}}\t{{.Status}}"

# 重置数据库（保留配置）
reset-db:
	@echo "警告：将删除所有数据！"
	@read -p "确认？(y/N) " confirm && [ "$$confirm" = "y" ] || exit 1
	cd backend && python scripts/init_db.py --reset
	@echo "数据库已重置"

# 备份数据
backup:
	@mkdir -p backups
	@BACKUP_NAME="backup_$$(date +%Y%m%d_%H%M%S)"; \
	mkdir -p "backups/$$BACKUP_NAME"; \
	cp -r backend/config/user_config.yaml "backups/$$BACKUP_NAME/" 2>/dev/null; \
	cp .env "backups/$$BACKUP_NAME/" 2>/dev/null; \
	cp "$${DATA_DIR:-$$HOME/.dierdanao/data}"/*.db "backups/$$BACKUP_NAME/" 2>/dev/null; \
	echo "备份完成: backups/$$BACKUP_NAME"

# 从备份恢复
restore:
	@echo "可用备份:"
	@ls -la backups/ 2>/dev/null || echo "无备份"
	@echo "用法: cp backups/<备份名>/* 到对应位置"
