"""Tag system Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- Tree tags (folder structure) ---

class TagTreeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    icon: str | None = None
    sort_order: int = 0


class TagTreeUpdate(BaseModel):
    name: str | None = None
    parent_id: str | None = None
    icon: str | None = None
    sort_order: int | None = None


class TagTreeOut(BaseModel):
    id: str
    name: str
    parent_id: str | None
    path: str
    icon: str | None
    sort_order: int
    created_at: str
    updated_at: str
    children: list[TagTreeOut] = []


# --- Content tags (flat) ---

class ContentTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str | None = None


class ContentTagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class ContentTagOut(BaseModel):
    id: str
    name: str
    color: str | None
    usage_count: int
    created_at: str


# --- Status dimensions ---

class StatusDimensionCreate(BaseModel):
    key: str = Field(min_length=1, max_length=50)
    display_name: str | None = None
    options: list[str]
    default_value: str | None = None


class StatusDimensionUpdate(BaseModel):
    display_name: str | None = None
    options: list[str] | None = None
    default_value: str | None = None


class StatusDimensionOut(BaseModel):
    id: str
    key: str
    display_name: str | None
    options: list[str]
    default_value: str | None
    created_at: str
