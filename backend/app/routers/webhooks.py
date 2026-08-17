"""Webhook endpoints called by Zapier.

Both are signature-verified (app/security.py) and both are idempotent, because
Zapier retries on any non-2xx and Gmail triggers can redeliver.
"""

from __future__ import annotations

import base64
import binascii
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.ingest import process_bid_email, process_purchase_order
from app.security import verify_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# A PO attachment that does not arrive quickly is a problem to surface, not to
# wait out -- Zapier's own step timeout is short.
ATTACHMENT_TIMEOUT_SECONDS = 20.0
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024


class BidRequestWebhook(BaseModel):
    message_id: str = Field(
        description="Gmail message id. The idempotency key is derived from it."
    )
    subject: str = ""
    body: str
    sender: str | None = None
    received_at: str | None = None
    email_link: str | None = None


class PurchaseOrderWebhook(BaseModel):
    message_id: str
    subject: str | None = None
    body: str | None = None
    #: Zapier exposes attachments as short-lived URLs; either form works.
    pdf_url: str | None = None
    pdf_base64: str | None = None


def _fetch_pdf(url: str) -> bytes:
    try:
        response = httpx.get(
            url, timeout=ATTACHMENT_TIMEOUT_SECONDS, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"could not fetch attachment: {exc}",
        ) from exc

    if len(response.content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="attachment exceeds 20MB",
        )
    return response.content


@router.post("/bid-request", dependencies=[Depends(verify_signature)])
def bid_request(payload: BidRequestWebhook) -> dict:
    """Bid-request email -> one Airtable record per property/lot."""
    result = process_bid_email(
        message_id=payload.message_id,
        subject=payload.subject,
        body=payload.body,
        sender=payload.sender,
        received_at=payload.received_at,
        email_link=payload.email_link,
    )
    return result.as_dict()


@router.post("/purchase-order", dependencies=[Depends(verify_signature)])
def purchase_order(payload: PurchaseOrderWebhook) -> dict:
    """PO email/PDF -> matched to an existing bid, 50% deposit computed."""
    if not (payload.body or payload.pdf_url or payload.pdf_base64):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="need one of body, pdf_url or pdf_base64",
        )

    pdf_bytes: bytes | None = None
    if payload.pdf_base64:
        try:
            pdf_bytes = base64.b64decode(payload.pdf_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"pdf_base64 is not valid base64: {exc}",
            ) from exc
    elif payload.pdf_url:
        pdf_bytes = _fetch_pdf(payload.pdf_url)

    result = process_purchase_order(
        message_id=payload.message_id,
        subject=payload.subject,
        body=payload.body,
        pdf_bytes=pdf_bytes,
    )
    return result.as_dict()
