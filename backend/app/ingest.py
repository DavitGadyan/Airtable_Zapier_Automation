"""Ingest orchestration: extract -> decide -> write -> audit.

The routers stay thin; this is where the actual sequencing lives, so it can be
exercised without an HTTP client.

One ordering decision worth calling out: the idempotency check happens *before*
extraction, not after. A Zapier retry storm on a six-lot email would otherwise
re-run the model every time and bill for it. Checking first makes a replay
free as well as harmless.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Any

from app.airtable import client as at
from app.airtable.client import AirtableRepository
from app.config import get_settings
from app.extraction.bid_extractor import extract_bids
from app.extraction.client import ExtractionRefused
from app.extraction.po_extractor import extract_purchase_order
from app.extraction.schemas import BidRequestBatch, ExtractedBid, ExtractedPurchaseOrder
from app.matching.fingerprint import idempotency_key, job_fingerprint
from app.matching.matcher import MatchMethod, match_purchase_order
from app.matching.revision import Action, Decision, classify
from app.pipeline import Stage, deposit_amount

logger = logging.getLogger(__name__)


@dataclass
class RecordOutcome:
    action: str
    reason: str
    record_id: str | None = None
    needs_review: bool = False
    label: str = ""


@dataclass
class IngestResult:
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    flagged: int = 0
    outcomes: list[RecordOutcome] = dc_field(default_factory=list)
    cost_usd: float = 0.0
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "flagged_for_review": self.flagged,
            "cost_usd": round(self.cost_usd, 6),
            "detail": self.detail,
            "outcomes": [
                {
                    "label": o.label,
                    "action": o.action,
                    "reason": o.reason,
                    "record_id": o.record_id,
                    "needs_review": o.needs_review,
                }
                for o in self.outcomes
            ],
        }


def _bid_label(bid: ExtractedBid) -> str:
    return f"{bid.property_name} - {bid.lot_number}" if bid.lot_number else bid.property_name


def _bid_fields(bid: ExtractedBid, batch: BidRequestBatch) -> dict[str, Any]:
    return {
        at.F_BID_NAME: _bid_label(bid),
        at.F_LOT: bid.lot_number,
        at.F_ADDRESS: bid.address,
        at.F_CITY: bid.city,
        at.F_STATE: bid.state,
        at.F_SCOPE: bid.scope_of_work,
        at.F_DUE_DATE: bid.bid_due_date.isoformat() if bid.bid_due_date else None,
        at.F_ESTIMATOR: None,
        at.F_CONFIDENCE: round(bid.confidence, 2),
    }


def process_bid_email(
    *,
    message_id: str,
    subject: str,
    body: str,
    sender: str | None = None,
    received_at: str | None = None,
    email_link: str | None = None,
    repo: AirtableRepository | None = None,
) -> IngestResult:
    """One bid-request email -> N Airtable records."""
    repo = repo or at.get_repository()
    result = IngestResult()

    # --- idempotency, before spending anything -------------------------
    if repo.find_by_idempotency_key(at.T_BIDS, idempotency_key(message_id, 0)):
        result.detail = "Already processed; no model call made."
        result.skipped = 1
        return result

    try:
        extraction = extract_bids(
            subject=subject, body=body, sender=sender, received_at=received_at
        )
    except ExtractionRefused as exc:
        repo.log_run(
            event="bid_extraction_refused",
            decision="error",
            reason=str(exc),
            source_message_id=message_id,
            raw_payload={"subject": subject},
        )
        result.detail = f"Model declined this email: {exc}"
        result.flagged = 1
        return result

    batch: BidRequestBatch = extraction.parsed
    result.cost_usd = extraction.usage.cost_usd
    result.detail = batch.summary

    open_bids = repo.open_bids()

    for index, bid in enumerate(batch.bids):
        result.processed += 1
        decision = classify(bid, batch.intent, open_bids)
        outcome = _apply_bid_decision(
            decision=decision,
            bid=bid,
            batch=batch,
            index=index,
            message_id=message_id,
            email_link=email_link,
            repo=repo,
        )
        result.outcomes.append(outcome)

        if outcome.action == Action.CREATE.value:
            result.created += 1
        elif outcome.action == Action.UPDATE.value:
            result.updated += 1
        elif outcome.action == Action.NO_OP.value:
            result.skipped += 1
        if outcome.needs_review:
            result.flagged += 1

    repo.log_run(
        event="bid_email_processed",
        decision="create" if result.created else "review",
        reason=batch.summary,
        source_message_id=message_id,
        usage=extraction.usage,
        raw_payload={"subject": subject, "sender": sender},
    )
    return result


def _apply_bid_decision(
    *,
    decision: Decision,
    bid: ExtractedBid,
    batch: BidRequestBatch,
    index: int,
    message_id: str,
    email_link: str | None,
    repo: AirtableRepository,
) -> RecordOutcome:
    label = _bid_label(bid)
    base_fields = _bid_fields(bid, batch)
    provenance = {
        at.F_SOURCE_MESSAGE_ID: message_id,
        at.F_SOURCE_LINK: email_link,
        at.F_IDEMPOTENCY: idempotency_key(message_id, index),
    }

    # --- needs a human --------------------------------------------------
    if decision.action is Action.REVIEW or decision.requires_confirmation:
        # A review item is still written to the base -- parked, not dropped.
        # An unwritten item is one nobody can find.
        if decision.target_bid_id:
            repo.update_bid(
                decision.target_bid_id,
                {at.F_NEEDS_REVIEW: True, at.F_REVIEW_REASON: decision.reason},
            )
            record_id = decision.target_bid_id
        else:
            record = repo.create_bid(
                {
                    **base_fields,
                    **provenance,
                    at.F_FINGERPRINT: job_fingerprint(
                        bid.property_name, bid.lot_number
                    ),
                    at.F_STATUS: Stage.BID_REQUEST.value,
                    at.F_NEEDS_REVIEW: True,
                    at.F_REVIEW_REASON: decision.reason,
                }
            )
            record_id = record["id"]

        repo.log_run(
            event="bid_flagged_for_review",
            decision="review",
            reason=decision.reason,
            source_message_id=message_id,
            bid_ids=[record_id],
            confidence=bid.confidence,
            changed_fields=decision.changed_fields or None,
        )
        return RecordOutcome(
            action=Action.REVIEW.value,
            reason=decision.reason,
            record_id=record_id,
            needs_review=True,
            label=label,
        )

    # --- straightforward paths -----------------------------------------
    if decision.action is Action.CREATE:
        record = repo.create_bid(
            {
                **base_fields,
                **provenance,
                at.F_FINGERPRINT: job_fingerprint(bid.property_name, bid.lot_number),
                at.F_STATUS: Stage.BID_REQUEST.value,
                at.F_NEEDS_REVIEW: False,
            }
        )
        repo.log_run(
            event="bid_created",
            decision="create",
            reason=decision.reason,
            source_message_id=message_id,
            bid_ids=[record["id"]],
            confidence=bid.confidence,
        )
        return RecordOutcome(
            action=Action.CREATE.value,
            reason=decision.reason,
            record_id=record["id"],
            label=label,
        )

    if decision.action is Action.UPDATE:
        # Previous values reach the audit trail BEFORE the write, so an
        # interrupted update still leaves the old state recoverable.
        repo.log_run(
            event="bid_revised",
            decision="update",
            reason=decision.reason,
            source_message_id=message_id,
            bid_ids=[decision.target_bid_id] if decision.target_bid_id else None,
            confidence=bid.confidence,
            changed_fields=decision.changed_fields,
        )
        repo.update_bid(
            decision.target_bid_id,
            {name: change["to"] for name, change in _to_airtable(decision).items()},
        )
        return RecordOutcome(
            action=Action.UPDATE.value,
            reason=decision.reason,
            record_id=decision.target_bid_id,
            label=label,
        )

    if decision.action is Action.CANCEL:
        repo.cancel_bid(decision.target_bid_id, decision.reason)
        repo.log_run(
            event="bid_cancelled",
            decision="cancel",
            reason=decision.reason,
            source_message_id=message_id,
            bid_ids=[decision.target_bid_id],
        )
        return RecordOutcome(
            action=Action.CANCEL.value,
            reason=decision.reason,
            record_id=decision.target_bid_id,
            label=label,
        )

    return RecordOutcome(
        action=Action.NO_OP.value,
        reason=decision.reason,
        record_id=decision.target_bid_id,
        label=label,
    )


#: extraction field name -> Airtable column
_FIELD_TO_COLUMN = {
    "address": at.F_ADDRESS,
    "city": at.F_CITY,
    "state": at.F_STATE,
    "scope_of_work": at.F_SCOPE,
    "bid_due_date": at.F_DUE_DATE,
}


def _to_airtable(decision: Decision) -> dict[str, dict[str, Any]]:
    return {
        _FIELD_TO_COLUMN[name]: change
        for name, change in decision.changed_fields.items()
        if name in _FIELD_TO_COLUMN
    }


def process_purchase_order(
    *,
    message_id: str,
    subject: str | None = None,
    body: str | None = None,
    pdf_bytes: bytes | None = None,
    repo: AirtableRepository | None = None,
) -> IngestResult:
    """One PO -> matched to an existing bid, deposit computed."""
    repo = repo or at.get_repository()
    settings = get_settings()
    result = IngestResult()

    key = idempotency_key(message_id, 0)
    if repo.find_by_idempotency_key(at.T_POS, key):
        result.detail = "Already processed; no model call made."
        result.skipped = 1
        return result

    try:
        extraction = extract_purchase_order(
            subject=subject, body=body, pdf_bytes=pdf_bytes
        )
    except ExtractionRefused as exc:
        repo.log_run(
            event="po_extraction_refused",
            decision="error",
            reason=str(exc),
            source_message_id=message_id,
        )
        result.detail = f"Model declined this document: {exc}"
        result.flagged = 1
        return result

    po: ExtractedPurchaseOrder = extraction.parsed
    result.cost_usd = extraction.usage.cost_usd
    result.processed = 1

    match = match_purchase_order(po, repo.candidate_bids_for_po())
    result.cost_usd = round(result.cost_usd, 6)

    needs_review = (
        match.needs_review
        or po.confidence < settings.extraction_confidence_threshold
        or po.approved_amount is None
    )
    reason_parts = [match.reasoning]
    if po.confidence < settings.extraction_confidence_threshold:
        reason_parts.append(f"PO extraction confidence {po.confidence:.0%}.")
    if po.approved_amount is None:
        reason_parts.append("No approved amount could be read.")
    reason = " ".join(reason_parts)

    fields: dict[str, Any] = {
        at.F_PO_NUMBER: po.po_number,
        at.F_PO_AMOUNT: po.approved_amount,
        at.F_PO_DEPOSIT: (
            deposit_amount(po.approved_amount) if po.approved_amount else None
        ),
        at.F_PO_ISSUE_DATE: po.issue_date.isoformat() if po.issue_date else None,
        at.F_SOURCE_MESSAGE_ID: message_id,
        at.F_IDEMPOTENCY: key,
        at.F_PO_MATCH_METHOD: match.method.value,
        at.F_PO_MATCH_SCORE: round(match.score, 2),
        at.F_NEEDS_REVIEW: needs_review,
        at.F_REVIEW_REASON: reason if needs_review else None,
    }
    if match.bid_id:
        fields[at.F_PO_BID] = [match.bid_id]

    record = repo.create_purchase_order(fields)

    # Only advance the bid when the match is confident AND the money is
    # readable. A PO parked for review must not move the pipeline.
    if match.bid_id and not needs_review:
        repo.update_bid(match.bid_id, {at.F_STATUS: Stage.PO_RECEIVED.value})
        result.updated = 1

    if needs_review:
        result.flagged = 1

    repo.log_run(
        event="po_processed",
        decision="match" if match.matched else "review",
        reason=reason,
        source_message_id=message_id,
        bid_ids=[match.bid_id] if match.bid_id else None,
        usage=extraction.usage,
        confidence=po.confidence,
        raw_payload={"po_number": po.po_number, "method": match.method.value},
    )

    result.created = 1
    result.detail = (
        f"PO {po.po_number} matched via {match.method.value} "
        f"({match.score:.0%})."
        if match.matched
        else f"PO {po.po_number} could not be matched. {match.reasoning}"
    )
    result.outcomes.append(
        RecordOutcome(
            action="match" if match.matched else "review",
            reason=reason,
            record_id=record["id"],
            needs_review=needs_review,
            label=po.po_number,
        )
    )
    return result
