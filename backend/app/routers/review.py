"""The human-review queue.

Everything the system declined to do on its own ends up here. This is the
counterweight that makes the confidence thresholds safe to set conservatively:
being unsure is cheap, because it costs one click rather than a silent error.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.airtable import client as at
from app.airtable.client import get_repository
from app.pipeline import ORDERED_STAGES, Stage

router = APIRouter(tags=["review"])


class ReviewResolution(BaseModel):
    approve: bool
    note: str | None = None
    #: Optional corrections a reviewer made in the UI before approving.
    corrections: dict[str, str] | None = None


@router.get("/review-queue")
def review_queue() -> dict:
    repo = get_repository()
    items = repo.review_queue()
    return {"count": len(items), "items": items}


@router.get("/pipeline")
def pipeline() -> dict:
    """Stage-by-stage counts for the dashboard board."""
    repo = get_repository()
    counts = repo.pipeline_counts()
    return {
        "stages": [
            {"name": stage.value, "count": counts.get(stage.value, 0)}
            for stage in ORDERED_STAGES
        ],
        "total": sum(counts.values()),
    }


@router.post("/review/{record_id}/resolve")
def resolve(record_id: str, resolution: ReviewResolution) -> dict:
    """Approve or reject one queued item.

    Rejection sets Cancelled rather than deleting, for the same reason
    everything else here does: a mistaken rejection has to be undoable.
    """
    repo = get_repository()

    if not resolution.approve:
        repo.cancel_bid(
            record_id, resolution.note or "Rejected in review; record retained."
        )
        repo.log_run(
            event="review_rejected",
            decision="cancel",
            reason=resolution.note or "",
            bid_ids=[record_id],
        )
        return {"record_id": record_id, "status": Stage.CANCELLED.value}

    fields: dict = {at.F_NEEDS_REVIEW: False, at.F_REVIEW_REASON: None}
    if resolution.corrections:
        allowed = {
            at.F_LOT,
            at.F_ADDRESS,
            at.F_CITY,
            at.F_STATE,
            at.F_SCOPE,
            at.F_DUE_DATE,
            at.F_ESTIMATOR,
        }
        unknown = set(resolution.corrections) - allowed
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"not correctable here: {sorted(unknown)}",
            )
        fields.update(resolution.corrections)

    repo.update_bid(record_id, fields)
    repo.log_run(
        event="review_approved",
        decision="update",
        reason=resolution.note or "Approved in review.",
        bid_ids=[record_id],
        changed_fields=resolution.corrections or None,
    )
    return {"record_id": record_id, "approved": True}
