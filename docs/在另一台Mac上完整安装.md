# 在另一台 Mac 上安装第二大脑

只需 **3 步**，不需要懂代码。

---

## 第 1 步：打开「终端」

按 `Command + 空格`，输入 `终端`，回车打开。

---

## 第 2 步：复制粘贴以下命令，回车执行

```bash
cd ~ && git clone https://github.com/zhourui156897/Cursor_Test.git dierdanao && cd dierdanao && bash install.sh
```

> 如果提示输入用户名和密码：
> - 用户名：`zhourui156897`
> - 密码：输入 GitHub Personal Access Token（向管理员索取）

安装过程全自动，大约需要 5-10 分钟（取决于网速），完成后会看到「安装完成」提示。

---

## 第 3 步：启动

```bash
cd ~/dierdanao && bash start.sh
```

浏览器会自动打开，看到「第二大脑」界面即表示成功。

---

## 日常使用

| 操作 | 命令 |
|------|------|
| 启动服务 | `cd ~/dierdanao && bash start.sh` |
| 停止服务 | `cd ~/dierdanao && bash stop.sh` |
| 更新版本 | `cd ~/dierdanao && bash update.sh` |

> 更新后需要重启：先 `bash stop.sh`，再 `bash start.sh`。

---

## 首次配置

启动后在浏览器中打开 http://localhost:5173，进入 **设置 → LLM / 模型**，填写：

- **API 地址**：`https://api.openai.com/v1`（或其他提供商）
- **API Key**：向管理员索取
- **模型**：`gpt-4o`

点击「保存配置」即可开始使用。

---

## 常见问题

| 问题 | 解决方式 |
|------|---------|
| 提示 command not found: git | 终端执行 `xcode-select --install` 安装开发工具 |
| 安装过程中要求输入密码 | 这是 Mac 系统密码（开机密码），输入时不会显示字符，输完回车即可 |
| 智能对话提示「服务不可用」 | 进入 设置 → LLM 页面配置 API Key |
| 版本更新提示 | 进入 设置 → 版本更新 页面查看详情，或执行 `bash update.sh` |

---

## 环境要求

| 项目 | 要求 | 说明 |
|------|------|------|
| 系统 | macOS | Apple 同步功能仅支持 Mac |
| 磁盘 | 2GB+ 可用空间 | 代码 + 依赖 + 数据 |
| 网络 | 需联网 | 安装时需下载依赖 |

Python、Node.js 等工具会由安装脚本自动安装，无需手动操作。
