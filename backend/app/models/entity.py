"""Entity and version Pydantic models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content: str | None = None
    content_type: str = "text"
    source: str = "upload"
    source_id: str | None = None
    metadata: dict | None = None
    folder_tag_id: str | None = None
    content_tag_names: list[str] | None = None
    status_values: dict | None = None


class EntityUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    metadata: dict | None = None


class EntityOut(BaseModel):
    id: str
    source: str
    source_id: str | None
    title: str | None
    content: str | None
    content_type: str
    obsidian_path: str | None
    file_path: str | None
    metadata: dict | None
    current_version: int
    review_status: str
    created_by: str | None
    created_at: str
    updated_at: str
    tags: EntityTagsOut | None = None


class EntityTagsOut(BaseModel):
    folder_tag_path: str | None = None
    content_tags: list[str] = []
    status_values: dict = {}


class EntityVersionOut(BaseModel):
    id: str
    entity_id: str
    version_number: int
    title: str | None
    content: str | None
    metadata: dict | None
    tags_snapshot: dict | None
    change_source: str | None
    change_summary: str | None
    created_at: str


class StatusTimelineEntry(BaseModel):
    id: str
    entity_id: str
    dimension: str
    old_value: str | None
    new_value: str | None
    changed_by: str | None
    changed_at: str
    note: str | None


class EntityListParams(BaseModel):
    source: str | None = None
    review_status: str | None = None
    folder_tag_path: str | None = None
    content_tag: str | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 20
