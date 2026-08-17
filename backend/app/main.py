"""FastAPI application.

Owns exactly the three things Zapier is bad at -- splitting one email into
many records, fuzzy PO-to-bid matching, and telling a revision apart from a
duplicate. Everything else (triggers, notifications, routine field updates)
stays in Zapier where the client can maintain it without us.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import review, webhooks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

app = FastAPI(
    title="Construction Ops Automation",
    version="0.1.0",
    description=(
        "AI extraction and matching for an Airtable-based construction "
        "operations system."
    ),
)

# The dashboard is a separate origin. Configurable via CORS_ORIGINS, because
# the deployed one is on a real domain rather than the dev port.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router)
app.include_router(review.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Reports configuration state without echoing any secret.

    Deliberately shows which credentials are *present* rather than valid --
    proving a key works means spending money on every health check.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.extraction_model,
        "effort": settings.extraction_effort,
        "airtable_configured": bool(
            settings.airtable_api_key and settings.airtable_base_id
        ),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "webhook_signature_required": not settings.allow_unsigned_webhooks,
        "auto_cancellation_enabled": settings.enable_auto_cancellation,
        "demo_mode": settings.demo_mode,
    }
