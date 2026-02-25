# 在另一台 Mac 上完整安装第二大脑

本文档用于在**新 Mac** 上从零安装并运行第二大脑，保证与当前版本一致、可复现。

---

## 一、环境要求

| 项目 | 要求 |
|------|------|
| 系统 | macOS（Apple 同步、JXA 仅支持 Mac） |
| Python | **3.11+** |
| Node.js | **18+**（建议 20+） |
| Docker Desktop | 可选。若用 Milvus Standalone / Neo4j 需安装；若仅用 milvus-lite 可不用 |
| ffmpeg | 可选。视频转文字需本机安装：`brew install ffmpeg` |

---

## 二、获取代码与配置

1. **获取项目**（任选其一）  
   - 从 Git 克隆：`git clone <仓库地址> dierdanao && cd dierdanao`  
   - 或把当前机器上的整个项目目录拷贝到新 Mac（如 U 盘、云盘）

2. **复制环境配置**  
   ```bash
   cp .env.example .env
   # 按需修改 .env（数据目录、端口、LLM 地址等）
   ```

3. **复制用户配置（如不存在）**  
   ```bash
   cp backend/config/user_config.example.yaml backend/config/user_config.yaml
   ```

---

## 三、安装后端（Python）

```bash
cd backend

# 建议使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 方式 A：按锁定版本安装（推荐，与当前发布一致）
pip install -r requirements.txt
pip install -e .

# 方式 B：仅从 pyproject 安装（会拉取最新兼容版本）
# pip install -e .

# 初始化数据库
python scripts/init_db.py
```

安装完成后可执行 `python -c "from app.main import app; print('OK')"` 自检。

---

## 四、安装前端

```bash
cd frontend

# 使用 lockfile 安装，保证与当前版本一致
npm ci

# 若无 package-lock.json，则用
# npm install
```

---

## 五、启动服务

**方式 A：一键启动（需 Docker）**

```bash
cd /path/to/dierdanao
make start
```

会启动 Docker（Milvus/Neo4j）、后端、前端。前端默认 http://localhost:3000，后端 http://localhost:8000/docs。

**方式 B：仅用 milvus-lite（不启 Docker）**

1. 在 `.env` 中设置 `VECTOR_DB_MODE=milvus-lite`（已是默认则不用改）。
2. 终端 1 启动后端：
   ```bash
   cd backend && source .venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. 终端 2 启动前端：
   ```bash
   cd frontend && npm run dev
   ```
4. 浏览器打开前端提示的地址（一般为 http://localhost:5173）。

---

## 六、数据目录与权限

- 数据默认目录：`~/.dierdanao/data`（或 `.env` 中 `DATA_DIR` 指定路径）。  
- 首次运行前建议执行（避免智能对话等写库报错）：  
  ```bash
  chmod -R u+rwx ~/.dierdanao/data
  ```  
  若修改了 `DATA_DIR`，请对**该目录**执行上述命令。

详见根目录《使用说明.md》中「五、最佳实践：数据目录必须可写」。

---

## 七、版本与后续更新

- **后端依赖**：以 `backend/requirements.txt` 为准；项目依赖变更后，维护者会同步更新该文件。  
- **前端依赖**：以 `frontend/package-lock.json` 为准；新 Mac 上请使用 `npm ci` 安装。  
- **文档**：代码或安装步骤有变更时，会同步更新本文档与根目录《使用说明.md》。

在另一台 Mac 上按上述步骤即可完整安装并运行第二大脑；若某步报错，可对照《使用说明.md》和《功能清单与待办.md》排查。
