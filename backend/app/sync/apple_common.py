"""Shared constants for Apple sync (JXA)."""

# 用户可见提示：JXA 失败时前端与 Agent 统一展示
JXA_USER_MESSAGE = (
    "请确保后端在本机 Mac 上运行，且已授予终端/应用对「备忘录」「提醒事项」「日历」的访问权限。"
    "若在非 Mac 环境或远程服务器运行，Apple 同步与创建功能不可用。"
)


def is_apple_jxa_error(e: BaseException) -> bool:
    """判断是否为 Apple JXA 相关错误（用于返回统一用户提示）。"""
    msg = str(e).lower()
    return any(
        x in msg
        for x in ("jxa", "apple notes", "apple reminders", "apple calendar", "osascript", "timed out")
    )
