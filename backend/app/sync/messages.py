"""Shared user-facing messages for sync (e.g. JXA failures)."""

# Apple 同步/创建失败时返回给前端与 Agent 的明确说明
APPLE_JXA_USER_MESSAGE = (
    "请确保后端在本机 Mac 上运行，且已授予终端/应用对「备忘录」「提醒事项」「日历」的访问权限。"
    "若仍失败，请查看后端日志中的具体错误。"
)
