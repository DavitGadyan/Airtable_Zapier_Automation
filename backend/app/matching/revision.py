"""Revisions, additions and cancellations -- without duplicates or data loss.

This module exists because of one line in the client's brief:

    "Project managers frequently send changes to previous bid requests, so we
     also need a safe process for handling revisions, additions and
     cancellations without creating duplicates or accidentally deleting valid
     bids."

Three rules make that guarantee, and they are enforced here rather than left
to the caller's discipline:

  1. Nothing is ever deleted. A cancellation sets status to Cancelled and
     records who said so and where. The record, its history, and its links to
     POs and invoices all survive.

  2. Revisions are versioned, not overwritten. The previous field values are
     returned in `changed_fields` and written to the Run Log before the update
     lands, so "what did this bid say last Tuesday" is always answerable.

  3. Nothing uncertain auto-applies. Below the confidence threshold, against a
     committed bid, or on any cancellation, the decision carries
     `requires_confirmation` and goes to the review queue instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.config import get_settings
from app.extraction.schemas import EmailIntent, ExtractedBid
from app.matching.fingerprint import content_hash, job_fingerprint
from app.pipeline import Stage, is_committed, is_terminal

# Fields compared when deciding whether an inbound bid actually changed
# anything. Deliberately excludes derived and workflow fields (status,
# estimator, timestamps) -- a project manager re-sending a scope does not
# imply anything about who it is assigned to.
COMPARED_FIELDS = (
    "address",
    "city",
    "state",
    "scope_of_work",
    "bid_due_date",
)


class Action(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    NO_OP = "no_op"
    CANCEL = "cancel"
    REVIEW = "review"


@dataclass
class ExistingBid:
    """The live Airtable state for one job, as far as this decision needs it."""

    record_id: str
    property_name: str
    lot_number: str | None
    status: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    scope_of_work: str | None = None
    bid_due_date: str | None = None

    @property
    def fingerprint(self) -> str:
        return job_fingerprint(self.property_name, self.lot_number)


@dataclass
class Decision:
    action: Action
    reason: str
    target_bid_id: str | None = None
    requires_confirmation: bool = False
    #: field -> {"from": old, "to": new}. Written to the Run Log before update.
    changed_fields: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def auto_appliable(self) -> bool:
        return not self.requires_confirmation and self.action is not Action.REVIEW


def _normalise(value: Any) -> Any:
    """Compare a date object and its ISO string as equal, and treat empty
    string as absent -- otherwise every re-send looks like an edit."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def diff_fields(incoming: ExtractedBid, existing: ExistingBid) -> dict[str, dict[str, Any]]:
    """Field-level diff, oldest-value-preserving."""
    changes: dict[str, dict[str, Any]] = {}
    for name in COMPARED_FIELDS:
        new = _normalise(getattr(incoming, name, None))
        old = _normalise(getattr(existing, name, None))
        # A revision that omits a field it previously stated is treated as
        # "unchanged", not "cleared". Blanking a due date because the follow-up
        # email did not repeat it would be data loss dressed up as an update.
        if new is None:
            continue
        if new != old:
            changes[name] = {"from": old, "to": new}
    return changes


def find_existing(
    incoming: ExtractedBid, open_bids: list[ExistingBid]
) -> ExistingBid | None:
    """Locate the same physical job by fingerprint.

    Exact only. A near-miss here means "probably a new lot", and inventing a
    match would be the duplicate-or-clobber failure this module exists to
    prevent. Ambiguity is resolved by a human, not by a threshold.
    """
    target = job_fingerprint(incoming.property_name, incoming.lot_number)
    matches = [b for b in open_bids if b.fingerprint == target]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Ambiguous: caller turns this into a REVIEW via classify().
        return None
    return None


def count_matches(incoming: ExtractedBid, open_bids: list[ExistingBid]) -> int:
    target = job_fingerprint(incoming.property_name, incoming.lot_number)
    return sum(1 for b in open_bids if b.fingerprint == target)


def classify(
    incoming: ExtractedBid,
    intent: EmailIntent,
    open_bids: list[ExistingBid],
) -> Decision:
    """Decide what to do with one extracted bid.

    `intent` is the sender's framing, read off the email. It is a hint and
    nothing more: what actually happens is decided against live state, because
    a PM who writes "revised scope below" when no original was ever entered is
    describing a new bid, whatever they called it.
    """
    settings = get_settings()

    # --- Rule 3, first pass: uncertain extraction never auto-applies ----
    if incoming.confidence < settings.extraction_confidence_threshold:
        return Decision(
            action=Action.REVIEW,
            reason=(
                f"Extraction confidence {incoming.confidence:.0%} is below the "
                f"{settings.extraction_confidence_threshold:.0%} bar"
                + (
                    f" (unsure about: {', '.join(incoming.uncertain_fields)})"
                    if incoming.uncertain_fields
                    else ""
                )
            ),
            requires_confirmation=True,
        )

    if count_matches(incoming, open_bids) > 1:
        return Decision(
            action=Action.REVIEW,
            reason=(
                "More than one existing bid shares this property and lot. "
                "A human has to say which one this refers to."
            ),
            requires_confirmation=True,
        )

    existing = find_existing(incoming, open_bids)

    # --- No prior record for this job ----------------------------------
    if existing is None:
        if intent is EmailIntent.CANCELLATION:
            # Cancelling something that was never captured. Almost always
            # means the original email was missed -- worth a human look, and
            # certainly not worth creating a record just to cancel it.
            return Decision(
                action=Action.REVIEW,
                reason=(
                    "Email cancels a bid, but no matching bid exists. The "
                    "original request was probably never captured."
                ),
                requires_confirmation=True,
            )
        return Decision(
            action=Action.CREATE,
            reason=(
                "New property/lot with no existing bid."
                if intent is not EmailIntent.ADDITION
                else "Additional lot on a known property."
            ),
        )

    # --- Rule 1: cancellations flag, never delete ----------------------
    if intent is EmailIntent.CANCELLATION:
        committed = is_committed(existing.status)
        return Decision(
            action=Action.CANCEL,
            target_bid_id=existing.record_id,
            reason=(
                "Cancellation for a bid that already has a PO or later "
                "activity against it -- confirm before standing the crew down."
                if committed
                else "Cancellation for an open bid."
            ),
            # Deliberately not auto-applied. See ENABLE_AUTO_CANCELLATION in
            # config.py: a misread cancellation kills a live job and is not
            # recoverable from the email thread alone. A committed bid always
            # needs confirmation regardless of the flag.
            requires_confirmation=committed or not settings.enable_auto_cancellation,
        )

    if is_terminal(existing.status):
        return Decision(
            action=Action.REVIEW,
            target_bid_id=existing.record_id,
            reason=(
                f"Bid is {existing.status}. Reopening it is a decision for a "
                "person, not an inbox rule."
            ),
            requires_confirmation=True,
        )

    # --- Identical re-send: do nothing --------------------------------
    changes = diff_fields(incoming, existing)
    if not changes:
        return Decision(
            action=Action.NO_OP,
            target_bid_id=existing.record_id,
            reason="Already on file with these values; nothing changed.",
        )

    # --- Rule 2: a real revision, versioned ---------------------------
    committed = is_committed(existing.status)
    return Decision(
        action=Action.UPDATE,
        target_bid_id=existing.record_id,
        reason=(
            f"Revision to {existing.status or 'an open bid'}: "
            f"{', '.join(sorted(changes))} changed."
            + (
                " A PO is already attached, so the scope this would rewrite "
                "has been priced and accepted."
                if committed
                else ""
            )
        ),
        changed_fields=changes,
        requires_confirmation=committed,
    )


def content_signature(bid: ExtractedBid) -> str:
    """Stable hash of the compared fields, for cheap re-send detection at the
    ingest boundary before any Airtable read happens."""
    return content_hash(
        **{name: _normalise(getattr(bid, name, None)) for name in COMPARED_FIELDS}
    )
