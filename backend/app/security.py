"""Webhook authentication.

Zapier's "Webhooks by Zapier" action can send a custom header. We require an
HMAC-SHA256 of the raw request body keyed on a shared secret, so a leaked URL
alone is not enough to write into the client's Airtable base.
"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings

SIGNATURE_HEADER = "X-Signature"


def sign(body: bytes, secret: str) -> str:
    """Return the hex signature for a raw body. Used by tests and by the
    Zapier Code step documented in zapier/README.md."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def verify_signature(
    request: Request,
    x_signature: str | None = Header(default=None, alias=SIGNATURE_HEADER),
) -> None:
    """FastAPI dependency. Raises 401 unless the body signature matches."""
    settings = get_settings()

    if settings.allow_unsigned_webhooks:
        return

    if not settings.webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WEBHOOK_SECRET is not configured",
        )

    if not x_signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"missing {SIGNATURE_HEADER} header",
        )

    expected = sign(await request.body(), settings.webhook_secret)

    # compare_digest to avoid leaking the signature through timing.
    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="bad signature"
        )
