"""User and authentication Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    display_name: str | None = None
    role: str = "member"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str | None
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None


class UserInDB(UserOut):
    password_hash: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: int


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)
