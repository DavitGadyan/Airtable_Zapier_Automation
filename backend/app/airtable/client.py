"""Airtable reads and writes.

Everything that touches the base goes through here, so field names live in one
place and a schema rename is a single-file change rather than a hunt through
string literals.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

from pyairtable import Api
from pyairtable.formulas import match as at_match

from app.config import get_settings
from app.extraction.client import Usage
from app.matching.matcher import CandidateBid
from app.matching.revision import ExistingBid
from app.pipeline import ORDERED_STAGES, Stage

logger = logging.getLogger(__name__)

# --- table names --------------------------------------------------------
T_CLIENTS = "Clients"
T_PROPERTIES = "Properties"
T_BIDS = "Bids"
T_POS = "Purchase Orders"
T_INVOICES = "Invoices"
T_PAYMENTS = "Payments"
T_CREWS = "Crews"
T_MATERIALS = "Material Orders"
T_RUN_LOG = "Run Log"

# --- Bids fields --------------------------------------------------------
F_BID_NAME = "Bid Name"
F_LOT = "Lot / Unit"
F_ADDRESS = "Address"
F_CITY = "City"
F_STATE = "State"
F_SCOPE = "Scope of Work"
F_DUE_DATE = "Bid Due Date"
F_STATUS = "Status"
F_ESTIMATOR = "Estimator"
F_FINGERPRINT = "Job Fingerprint"
F_IDEMPOTENCY = "Idempotency Key"
F_SOURCE_MESSAGE_ID = "Source Message ID"
F_SOURCE_LINK = "Source Email Link"
F_CONFIDENCE = "Extraction Confidence"
F_NEEDS_REVIEW = "Needs Review"
F_REVIEW_REASON = "Review Reason"

# --- Purchase Orders fields --------------------------------------------
F_PO_NUMBER = "PO Number"
F_PO_AMOUNT = "Approved Amount"
F_PO_DEPOSIT = "Deposit Amount"
F_PO_ISSUE_DATE = "Issue Date"
F_PO_BID = "Bid"
F_PO_MATCH_METHOD = "Match Method"
F_PO_MATCH_SCORE = "Match Score"


class AirtableRepository:
    """Thin, explicit data layer. No ORM, no magic."""

    def __init__(self, api_key: str, base_id: str) -> None:
        self._api = Api(api_key)
        self._base_id = base_id

    def _table(self, name: str):
        return self._api.table(self._base_id, name)

    # --- reads ----------------------------------------------------------

    def _all_bids(self) -> list[dict[str, Any]]:
        return self._table(T_BIDS).all()

    def open_bids(self) -> list[ExistingBid]:
        """Bids that a revision or cancellation could legitimately target.

        Includes terminal ones deliberately: classify() needs to *see* a Closed
        bid to refuse to reopen it. Filtering them out here would make a
        revision against a closed job look like a brand new bid and silently
        create a duplicate -- the exact failure this system is built to avoid.
        """
        return [
            ExistingBid(
                record_id=record["id"],
                property_name=self._property_name(record),
                lot_number=record["fields"].get(F_LOT),
                status=record["fields"].get(F_STATUS),
                address=record["fields"].get(F_ADDRESS),
                city=record["fields"].get(F_CITY),
                state=record["fields"].get(F_STATE),
                scope_of_work=record["fields"].get(F_SCOPE),
                bid_due_date=record["fields"].get(F_DUE_DATE),
            )
            for record in self._all_bids()
        ]

    def candidate_bids_for_po(self) -> list[CandidateBid]:
        """Bids a PO could plausibly attach to.

        A PO arriving for a job already past `PO Received` is almost always a
        revised or duplicate PO for that same job, so those stay in the pool;
        only Lost and Cancelled are excluded, because attaching money to a dead
        job is never right.
        """
        excluded = {Stage.LOST.value, Stage.CANCELLED.value}
        return [
            CandidateBid(
                record_id=record["id"],
                property_name=self._property_name(record),
                lot_number=record["fields"].get(F_LOT),
                scope_of_work=record["fields"].get(F_SCOPE),
                status=record["fields"].get(F_STATUS),
            )
            for record in self._all_bids()
            if record["fields"].get(F_STATUS) not in excluded
        ]

    @staticmethod
    def _property_name(record: dict[str, Any]) -> str:
        """Bid Name is composed as 'Property - Lot'; recover the property half.

        The Property link field returns record ids rather than names, and
        resolving every one would be an N+1 against the API on a hot path.
        """
        name = record["fields"].get(F_BID_NAME) or ""
        return name.split(" - ")[0].strip() if " - " in name else name.strip()

    def find_by_idempotency_key(self, table: str, key: str) -> dict[str, Any] | None:
        rows = self._table(table).all(
            formula=at_match({F_IDEMPOTENCY: key}), max_records=1
        )
        return rows[0] if rows else None

    def review_queue(self) -> list[dict[str, Any]]:
        """Everything blocked on a human, newest first."""
        out: list[dict[str, Any]] = []
        for table_name in (T_BIDS, T_POS):
            for record in self._table(table_name).all(
                formula=at_match({F_NEEDS_REVIEW: 1})
            ):
                out.append(
                    {
                        "table": table_name,
                        "record_id": record["id"],
                        "created_time": record.get("createdTime"),
                        "reason": record["fields"].get(F_REVIEW_REASON),
                        "fields": record["fields"],
                    }
                )
        out.sort(key=lambda r: r.get("created_time") or "", reverse=True)
        return out

    def pipeline_counts(self) -> dict[str, int]:
        counts = {stage.value: 0 for stage in ORDERED_STAGES}
        for record in self._all_bids():
            status = record["fields"].get(F_STATUS)
            if status in counts:
                counts[status] += 1
        return counts

    # --- writes ---------------------------------------------------------

    def create_bid(self, fields: dict[str, Any]) -> dict[str, Any]:
        return self._table(T_BIDS).create(_drop_empty(fields))

    def update_bid(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        return self._table(T_BIDS).update(record_id, _drop_empty(fields))

    def create_purchase_order(self, fields: dict[str, Any]) -> dict[str, Any]:
        return self._table(T_POS).create(_drop_empty(fields))

    def cancel_bid(self, record_id: str, reason: str) -> dict[str, Any]:
        """Flag as Cancelled. Never deletes.

        The record, its history and its links to POs and invoices all survive,
        because "we cancelled the wrong lot" has to be recoverable in one click.
        """
        return self.update_bid(
            record_id,
            {
                F_STATUS: Stage.CANCELLED.value,
                F_REVIEW_REASON: reason,
                F_NEEDS_REVIEW: False,
            },
        )

    def log_run(
        self,
        *,
        event: str,
        decision: str,
        reason: str = "",
        source_message_id: str | None = None,
        bid_ids: Iterable[str] | None = None,
        usage: Usage | None = None,
        confidence: float | None = None,
        changed_fields: dict[str, Any] | None = None,
        raw_payload: Any = None,
    ) -> None:
        """Append to the audit trail.

        Never raises into the caller: a failure to write the log must not undo
        work that already succeeded. It is logged locally instead.
        """
        fields: dict[str, Any] = {
            "Event": event,
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "Decision": decision,
            "Reason": reason[:100_000],
        }
        if source_message_id:
            fields["Source Message ID"] = source_message_id
        if bid_ids:
            fields["Bid"] = list(bid_ids)
        if usage:
            fields["Model"] = usage.model
            fields["Input Tokens"] = usage.input_tokens
            fields["Output Tokens"] = usage.output_tokens
            fields["Cost USD"] = usage.cost_usd
        if confidence is not None:
            fields["Confidence"] = confidence
        if changed_fields:
            fields["Changed Fields"] = json.dumps(changed_fields, default=str)[:100_000]
        if raw_payload is not None:
            fields["Raw Payload"] = json.dumps(raw_payload, default=str)[:100_000]

        try:
            self._table(T_RUN_LOG).create(_drop_empty(fields))
        except Exception:  # noqa: BLE001 -- audit must never break ingest
            logger.exception("failed to write Run Log entry for %s", event)


def _drop_empty(fields: dict[str, Any]) -> dict[str, Any]:
    """Airtable rejects None for several field types; omitting the key means
    'leave unchanged', which is what we want everywhere here."""
    return {k: v for k, v in fields.items() if v is not None}


@lru_cache
def get_repository() -> AirtableRepository:
    settings = get_settings()
    if settings.demo_mode:
        # Imported lazily: app.demo imports this module for its field-name
        # constants, so a module-level import here would be circular.
        from app.demo import seeded_repository

        logger.warning("DEMO_MODE is on -- serving seeded in-memory data")
        return seeded_repository()  # type: ignore[return-value]
    return AirtableRepository(settings.airtable_api_key, settings.airtable_base_id)
