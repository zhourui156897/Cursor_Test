"""Review queue API: list pending, approve/reject/batch-approve tag suggestions."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import get_current_user
from app.models.user import UserOut
from app.models.review import (
    ReviewItemOut,
    ReviewApproveRequest,
    ReviewRejectRequest,
    ReviewBatchApproveRequest,
)
from app.services import review_service

router = APIRouter()


@router.get("/pending", response_model=list[ReviewItemOut])
async def list_pending_reviews(
    _: Annotated[UserOut, Depends(get_current_user)],
    page: int = 1,
):
    return await review_service.list_pending(page=page)


@router.get("/count")
async def get_pending_count(
    _: Annotated[UserOut, Depends(get_current_user)],
):
    count = await review_service.get_pending_count()
    return {"count": count}


@router.post("/{review_id}/approve")
async def approve_review(
    review_id: str,
    req: ReviewApproveRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    try:
        action = await review_service.approve_item(review_id, req.modifications)
        return {"message": "审核通过", "action": action}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{review_id}/reject")
async def reject_review(
    review_id: str,
    req: ReviewRejectRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    await review_service.reject_item(review_id, req.reason)
    return {"message": "已拒绝"}


@router.post("/batch-approve")
async def batch_approve_reviews(
    req: ReviewBatchApproveRequest,
    _: Annotated[UserOut, Depends(get_current_user)],
):
    count = await review_service.batch_approve(req.review_ids)
    return {"message": f"已批量通过 {count} 条", "approved_count": count}
