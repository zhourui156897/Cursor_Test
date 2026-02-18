"""Auth dependencies for FastAPI route injection."""

from __future__ import annotations

from functools import wraps
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings
from app.auth.jwt import decode_access_token
from app.storage.sqlite_client import get_db
from app.models.user import UserOut

_bearer_scheme = HTTPBearer(auto_error=False)

_SINGLE_MODE_ADMIN = UserOut(
    id="single-mode-admin",
    username="admin",
    display_name="管理员",
    role="admin",
    is_active=True,
    created_at="",
    last_login_at=None,
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> UserOut:
    settings = get_settings()

    if settings.auth_mode == "single":
        return _SINGLE_MODE_ADMIN

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供认证凭据")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的token")

    user_id = payload.get("sub")
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, display_name, role, is_active, created_at, last_login_at "
        "FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()

    if row is None or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return UserOut(**dict(row))


async def get_admin_user(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def require_permission(permission: str):
    async def _check(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
        if user.role == "admin":
            return user

        db = await get_db()
        cursor = await db.execute(
            "SELECT permission FROM role_permissions WHERE role = ?",
            (user.role,),
        )
        rows = await cursor.fetchall()
        user_permissions = {r["permission"] for r in rows}

        if "*" in user_permissions or permission in user_permissions:
            return user

        parts = permission.split(":")
        for i in range(len(parts)):
            wildcard = ":".join(parts[: i + 1]) + ":*"
            if wildcard in user_permissions:
                return user

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {permission}")

    return Depends(_check)
