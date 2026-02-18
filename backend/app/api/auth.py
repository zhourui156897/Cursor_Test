"""Authentication API: login, register, user management."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt

from app.auth.dependencies import get_current_user, get_admin_user
from app.auth.jwt import create_access_token
from app.config import get_settings
from app.models.user import (
    LoginRequest,
    Token,
    UserCreate,
    UserOut,
    UserUpdate,
    PasswordChange,
)
from app.storage.sqlite_client import get_db

router = APIRouter()


@router.get("/mode")
async def get_auth_mode():
    settings = get_settings()
    return {"auth_mode": settings.auth_mode}


@router.post("/login", response_model=Token)
async def login(req: LoginRequest):
    settings = get_settings()
    if settings.auth_mode == "single":
        return Token(access_token=create_access_token("single-mode-admin", "admin"))

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, password_hash, role, is_active FROM users WHERE username = ?",
        (req.username,),
    )
    user = await cursor.fetchone()

    if user is None or not bcrypt.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    if not user["is_active"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已被禁用")

    await db.execute(
        "UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
        (user["id"],),
    )
    await db.commit()

    return Token(access_token=create_access_token(user["id"], user["role"]))


@router.get("/me", response_model=UserOut)
async def get_me(user: Annotated[UserOut, Depends(get_current_user)]):
    return user


@router.put("/me/password")
async def change_password(
    req: PasswordChange,
    user: Annotated[UserOut, Depends(get_current_user)],
):
    db = await get_db()
    cursor = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user.id,))
    row = await cursor.fetchone()

    if row is None or not bcrypt.verify(req.old_password, row["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")

    new_hash = bcrypt.hash(req.new_password)
    await db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user.id))
    await db.commit()
    return {"message": "密码修改成功"}


@router.get("/users", response_model=list[UserOut])
async def list_users(_: Annotated[UserOut, Depends(get_admin_user)]):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, display_name, role, is_active, created_at, last_login_at FROM users ORDER BY created_at"
    )
    rows = await cursor.fetchall()
    return [UserOut(**dict(r)) for r in rows]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    req: UserCreate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (req.username,))
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="用户名已存在")

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hash(req.password)

    await db.execute(
        "INSERT INTO users (id, username, password_hash, display_name, role) VALUES (?, ?, ?, ?, ?)",
        (user_id, req.username, password_hash, req.display_name or req.username, req.role),
    )
    await db.commit()

    return UserOut(
        id=user_id,
        username=req.username,
        display_name=req.display_name or req.username,
        role=req.role,
        is_active=True,
        created_at="",
        last_login_at=None,
    )


@router.put("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    req: UserUpdate,
    _: Annotated[UserOut, Depends(get_admin_user)],
):
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, username, display_name, role, is_active, created_at, last_login_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    updates = {}
    if req.display_name is not None:
        updates["display_name"] = req.display_name
    if req.role is not None:
        updates["role"] = req.role
    if req.is_active is not None:
        updates["is_active"] = req.is_active

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        await db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        await db.commit()

    cursor = await db.execute(
        "SELECT id, username, display_name, role, is_active, created_at, last_login_at FROM users WHERE id = ?",
        (user_id,),
    )
    updated = await cursor.fetchone()
    return UserOut(**dict(updated))


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: Annotated[UserOut, Depends(get_admin_user)],
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    db = await get_db()
    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()
    return {"message": "用户已删除"}
