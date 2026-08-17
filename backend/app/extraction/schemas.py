"""Extraction schemas.

These Pydantic models ARE the structured-output schemas handed to the Claude
API. Validation happens at the tool-call layer, so the model is forced to
retry on a mismatch and we never hand-parse JSON or regex a response.

A note on confidence. The obvious design is a `*_confidence: float` beside
every field. We deliberately do not do that: LLM-emitted per-field floats are
poorly calibrated, and eight extra floats per bid is real output-token spend on
a per-email cost line that we quote to the client. One calibrated record-level
score plus an explicit `uncertain_fields` list drives the review UI exactly as
well -- it tells the reviewer *which* box to look at -- at a fraction of the
tokens.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    """Structured outputs require `additionalProperties: false` everywhere."""

    model_config = ConfigDict(extra="forbid")


class EmailIntent(str, Enum):
    """What the sender is trying to do.

    Read off the email itself. This is only a *hint* -- the authoritative
    new/revision/cancellation decision is made in app.matching.revision after
    comparing against what is already in Airtable, because the sender's
    framing and the database state routinely disagree.
    """

    NEW_REQUEST = "new_request"
    REVISION = "revision"
    ADDITION = "addition"
    CANCELLATION = "cancellation"
    UNCLEAR = "unclear"


class ExtractedBid(_Strict):
    """One property/lot from a bid-request email.

    One email frequently contains several of these -- that multiplication is
    the single most valuable thing the extraction step does.
    """

    property_name: str = Field(
        description="Subdivision, community, or property name, e.g. 'Willow Creek'."
    )
    lot_number: str | None = Field(
        default=None,
        description="Lot or unit identifier exactly as written, e.g. 'Lot 42', '12B'.",
    )
    address: str | None = Field(
        default=None, description="Street address if stated."
    )
    city: str | None = Field(default=None)
    state: str | None = Field(
        default=None, description="Two-letter US state code, uppercase."
    )
    scope_of_work: str = Field(
        description="What work is being requested, in the sender's own terms."
    )
    bid_due_date: date | None = Field(
        default=None, description="Date the bid is due back, if stated."
    )
    confidence: float = Field(
        description=(
            "0.0-1.0. How confident you are that this is a genuine, distinct "
            "bid request with correctly attributed fields. Be honest: a low "
            "score routes to human review, which is cheap. A wrong high score "
            "is not."
        )
    )
    uncertain_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Names of fields above you are unsure about. Empty list if none. "
            "Use the exact field names, e.g. ['lot_number', 'bid_due_date']."
        ),
    )


class BidRequestBatch(_Strict):
    """Everything extracted from one email."""

    project_manager: str | None = Field(
        default=None, description="Name of the project manager / sender."
    )
    client_company: str | None = Field(
        default=None, description="Company the project manager works for."
    )
    intent: EmailIntent = Field(
        description="What this email is doing relative to any previous request."
    )
    bids: list[ExtractedBid] = Field(
        description=(
            "One entry per distinct property/lot. An email listing six lots "
            "produces six entries. Never merge distinct lots into one entry."
        )
    )
    summary: str = Field(
        description="One sentence a human can scan in the review queue."
    )


class ExtractedPurchaseOrder(_Strict):
    """A PO, read from an email body or an attached PDF."""

    po_number: str = Field(description="The purchase order number.")
    property_name: str | None = Field(default=None)
    lot_number: str | None = Field(default=None)
    address: str | None = Field(default=None)
    approved_amount: float | None = Field(
        default=None, description="Approved dollar amount, numeric, no symbols."
    )
    scope_of_work: str | None = Field(default=None)
    issue_date: date | None = Field(default=None)
    confidence: float = Field(description="0.0-1.0, as above.")
    uncertain_fields: list[str] = Field(default_factory=list)


class MatchAdjudication(_Strict):
    """Returned by the LLM tie-break in app.matching.matcher.

    Only invoked when deterministic and fuzzy matching leave more than one
    plausible candidate -- see the tiering comment there.
    """

    chosen_bid_id: str | None = Field(
        default=None,
        description=(
            "The record id of the single best-matching bid, or null if none of "
            "the candidates is a convincing match. Null is a valid, and often "
            "correct, answer."
        ),
    )
    confidence: float = Field(description="0.0-1.0 in the chosen match.")
    reasoning: str = Field(
        description="One or two sentences. Shown to a human in the review queue."
    )
