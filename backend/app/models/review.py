"""Pydantic models for the review queue."""

from __future__ import annotations

from pydantic import BaseModel


class ReviewItemOut(BaseModel):
    id: str
    entity_id: str
    entity_title: str | None = None
    entity_source: str | None = None
    entity_content: str | None = None
    suggested_folder_tags: list[str] | dict | None = None
    suggested_content_tags: list[str] | dict | None = None
    suggested_status: dict | None = None
    confidence_scores: dict | None = None
    status: str
    reviewer_action: dict | None = None
    created_at: str | None = None
    reviewed_at: str | None = None


class ReviewApproveRequest(BaseModel):
    modifications: dict | None = None


class ReviewRejectRequest(BaseModel):
    reason: str = ""


class ReviewBatchApproveRequest(BaseModel):
    review_ids: list[str]
