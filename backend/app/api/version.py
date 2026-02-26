"""版本管理 API：本地版本查询 + GitHub 远程版本检查。"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)

_VERSION_FILE = Path(__file__).resolve().parent.parent.parent.parent / "VERSION"
_GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/zhourui156897/Cursor_Test/main/VERSION"
)


def get_local_version() -> str:
    """读取项目根目录 VERSION 文件，返回版本字符串。"""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return "unknown"


@router.get("")
async def version():
    """返回本地版本号。"""
    return {"version": get_local_version()}


@router.get("/check")
async def check_update():
    """对比本地版本与 GitHub main 分支上的 VERSION，判断是否有更新。"""
    local = get_local_version()
    remote = local  # 默认与本地相同
    has_update = False
    error: str | None = None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(_GITHUB_RAW_URL)
            if resp.status_code == 200:
                remote = resp.text.strip()
                has_update = remote != local
            else:
                error = f"GitHub 返回 {resp.status_code}"
    except Exception as e:
        logger.warning("检查远程版本失败: %s", e)
        error = str(e)

    return {
        "local": local,
        "remote": remote,
        "has_update": has_update,
        "error": error,
    }
