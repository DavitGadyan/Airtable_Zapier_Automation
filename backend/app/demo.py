"""In-memory repository and seed data.

Serves two purposes that turn out to be the same thing:

  * the test suite needs a repository it can drive without an Airtable account
  * a demo needs a dashboard with something on it, without live credentials

Keeping one implementation for both means the thing being demonstrated is the
same code path that is tested, rather than a mock that has quietly drifted.

Enable with `DEMO_MODE=true`. It is off by default and the flag is reported by
`/health`, so a service accidentally left in demo mode is visible rather than
silently serving fiction.
"""

from __future__ import annotations

import itertools
from datetime import date, timedelta
from typing import Any

from app.airtable import client as at
from app.matching.fingerprint import idempotency_key, job_fingerprint
from app.matching.matcher import CandidateBid
from app.matching.revision import ExistingBid
from app.pipeline import Stage


class InMemoryRepository:
    """Mirrors AirtableRepository's method signatures exactly.

    If the two drift, the e2e tests keep passing while production breaks --
    treat a change to one as a change to both.
    """

    def __init__(self) -> None:
        self.bids: dict[str, dict[str, Any]] = {}
        self.purchase_orders: dict[str, dict[str, Any]] = {}
        self.run_log: list[dict[str, Any]] = []
        self._ids = itertools.count(1)

    def _next_id(self, prefix: str) -> str:
        return f"{prefix}{next(self._ids):05d}"

    # --- reads ----------------------------------------------------------

    @staticmethod
    def _property_of(fields: dict[str, Any]) -> str:
        name = fields.get(at.F_BID_NAME) or ""
        return name.split(" - ")[0].strip() if " - " in name else name.strip()

    def open_bids(self) -> list[ExistingBid]:
        return [
            ExistingBid(
                record_id=rid,
                property_name=self._property_of(f),
                lot_number=f.get(at.F_LOT),
                status=f.get(at.F_STATUS),
                address=f.get(at.F_ADDRESS),
                city=f.get(at.F_CITY),
                state=f.get(at.F_STATE),
                scope_of_work=f.get(at.F_SCOPE),
                bid_due_date=f.get(at.F_DUE_DATE),
            )
            for rid, f in self.bids.items()
        ]

    def candidate_bids_for_po(self) -> list[CandidateBid]:
        excluded = {Stage.LOST.value, Stage.CANCELLED.value}
        return [
            CandidateBid(
                record_id=rid,
                property_name=self._property_of(f),
                lot_number=f.get(at.F_LOT),
                scope_of_work=f.get(at.F_SCOPE),
                status=f.get(at.F_STATUS),
            )
            for rid, f in self.bids.items()
            if f.get(at.F_STATUS) not in excluded
        ]

    def find_by_idempotency_key(self, table: str, key: str) -> dict[str, Any] | None:
        store = self.bids if table == at.T_BIDS else self.purchase_orders
        for rid, fields in store.items():
            if fields.get(at.F_IDEMPOTENCY) == key:
                return {"id": rid, "fields": fields}
        return None

    def review_queue(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for table_name, store in ((at.T_BIDS, self.bids), (at.T_POS, self.purchase_orders)):
            for rid, f in store.items():
                if f.get(at.F_NEEDS_REVIEW):
                    out.append(
                        {
                            "table": table_name,
                            "record_id": rid,
                            "created_time": f.get("_created", ""),
                            "reason": f.get(at.F_REVIEW_REASON),
                            "fields": {k: v for k, v in f.items() if not k.startswith("_")},
                        }
                    )
        return out

    def pipeline_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fields in self.bids.values():
            status = fields.get(at.F_STATUS)
            if status:
                counts[status] = counts.get(status, 0) + 1
        return counts

    # --- writes ---------------------------------------------------------

    def create_bid(self, fields: dict[str, Any]) -> dict[str, Any]:
        rid = self._next_id("recBID")
        self.bids[rid] = {k: v for k, v in fields.items() if v is not None}
        return {"id": rid, "fields": self.bids[rid]}

    def update_bid(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        self.bids[record_id].update({k: v for k, v in fields.items() if v is not None})
        return {"id": record_id, "fields": self.bids[record_id]}

    def create_purchase_order(self, fields: dict[str, Any]) -> dict[str, Any]:
        rid = self._next_id("recPO")
        self.purchase_orders[rid] = {k: v for k, v in fields.items() if v is not None}
        return {"id": rid, "fields": self.purchase_orders[rid]}

    def cancel_bid(self, record_id: str, reason: str) -> dict[str, Any]:
        return self.update_bid(
            record_id,
            {
                at.F_STATUS: Stage.CANCELLED.value,
                at.F_REVIEW_REASON: reason,
                at.F_NEEDS_REVIEW: False,
            },
        )

    def log_run(self, **kwargs: Any) -> None:
        self.run_log.append(kwargs)

    # --- helpers --------------------------------------------------------

    def events(self) -> list[str]:
        return [entry.get("event", "") for entry in self.run_log]


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_TODAY = date(2026, 8, 18)


def _bid(
    prop: str,
    lot: str,
    status: Stage,
    scope: str,
    *,
    city: str = "Boise",
    state: str = "ID",
    address: str | None = None,
    due_in_days: int = 14,
    confidence: float = 0.95,
    needs_review: bool = False,
    review_reason: str | None = None,
    message_id: str = "demo-seed",
    index: int = 0,
) -> dict[str, Any]:
    return {
        at.F_BID_NAME: f"{prop} - {lot}",
        at.F_LOT: lot,
        at.F_ADDRESS: address,
        at.F_CITY: city,
        at.F_STATE: state,
        at.F_SCOPE: scope,
        at.F_DUE_DATE: (_TODAY + timedelta(days=due_in_days)).isoformat(),
        at.F_STATUS: status.value,
        at.F_FINGERPRINT: job_fingerprint(prop, lot),
        at.F_IDEMPOTENCY: idempotency_key(message_id, index),
        at.F_SOURCE_MESSAGE_ID: message_id,
        at.F_CONFIDENCE: confidence,
        at.F_NEEDS_REVIEW: needs_review,
        at.F_REVIEW_REASON: review_reason,
    }


def seed(repo: InMemoryRepository) -> InMemoryRepository:
    """Populate a repository with a plausible week of work.

    Shaped to show the things that matter rather than to look impressive: jobs
    spread across the pipeline, two stages carrying work that is stuck, and a
    review queue containing one of each kind of doubt the system can have.
    """
    # The six-lot email from the fixtures, now spread across the pipeline the
    # way a real week would leave it.
    willow = "Willow Creek Phase 2"
    for i, (lot, status, addr) in enumerate(
        [
            ("Lot 41", Stage.BID_SUBMITTED, "1187 Alder Run Ct"),
            ("Lot 42", Stage.PO_RECEIVED, "1191 Alder Run Ct"),
            ("Lot 43", Stage.BID_ASSIGNED, "1195 Alder Run Ct"),
            ("Lot 45", Stage.BID_REQUEST, "1203 Alder Run Ct"),
            ("Lot 46", Stage.BID_SUBMITTED, "1207 Alder Run Ct"),
        ]
    ):
        repo.create_bid(
            _bid(
                willow,
                lot,
                status,
                "R&R carpet & pad t/o, LVP in both baths",
                address=addr,
                message_id="CAF7z1-multi-lot-001",
                index=i,
            )
        )

    # Lot 44 was cancelled by a follow-up email. Retained, never deleted --
    # which is the whole point of it appearing here at all.
    repo.create_bid(
        _bid(
            willow,
            "Lot 44",
            Stage.CANCELLED,
            "carpet & pad t/o only",
            address="1199 Alder Run Ct",
            review_reason="Cancelled by PM 16 Aug: 'buyer backed out'. Record retained.",
            message_id="CAF7z1-revision-002",
            index=3,
        )
    )

    # Other properties, at later stages.
    later = [
        ("Harbor Point", "Lot 7", Stage.DEPOSIT_PAID, "LVP throughout, tile entry"),
        ("Harbor Point", "Lot 9", Stage.CREW_ASSIGNED, "Carpet bedrooms, LVP living"),
        ("Copper Ridge", "12B", Stage.SCHEDULED, "R&R carpet, stair runner"),
        ("Copper Ridge", "14A", Stage.IN_PROGRESS, "Full flooring package"),
        ("Sagebrush Commons", "Lot 3", Stage.COMPLETED, "LVP throughout"),
        ("Sagebrush Commons", "Lot 5", Stage.COMPLETED, "Carpet & pad, LVP baths"),
        ("Sagebrush Commons", "Lot 6", Stage.FINAL_INVOICE_SENT, "LVP throughout"),
        ("Meridian Park", "Lot 22", Stage.FINAL_PAYMENT_RECEIVED, "Carpet t/o"),
        ("Meridian Park", "Lot 24", Stage.CLOSED, "Carpet t/o, LVP entry"),
        ("Kestrel Landing", "Lot 8", Stage.MATERIALS_ORDERED, "LVP + tile master bath"),
        ("Kestrel Landing", "Lot 11", Stage.DEPOSIT_INVOICE_SENT, "Carpet & pad t/o"),
    ]
    for i, (prop, lot, status, scope) in enumerate(later):
        repo.create_bid(
            _bid(prop, lot, status, scope, message_id="demo-seed-later", index=i)
        )

    # --- the review queue: one of each kind of doubt --------------------

    # 1. Low-confidence extraction from a forwarded scan.
    repo.create_bid(
        _bid(
            "Harbor Point",
            "Lot 12",
            Stage.BID_REQUEST,
            "unclear - possibly LVP, possibly carpet",
            confidence=0.42,
            needs_review=True,
            review_reason=(
                "Extraction confidence 42% is below the 80% bar "
                "(unsure about: scope_of_work, bid_due_date)"
            ),
            message_id="demo-review-1",
        )
    )

    # 2. A cancellation, detected and deliberately not applied.
    repo.create_bid(
        _bid(
            "Copper Ridge",
            "16C",
            Stage.BID_SUBMITTED,
            "R&R carpet t/o",
            needs_review=True,
            review_reason=(
                "Cancellation for an open bid. Detected but never auto-applied: "
                "a misread cancellation stands a crew down on a live job."
            ),
            message_id="demo-review-2",
        )
    )

    # 3. A PO that could not be matched confidently.
    repo.create_purchase_order(
        {
            at.F_PO_NUMBER: "PO-10088",
            at.F_PO_AMOUNT: 8_400.00,
            at.F_PO_DEPOSIT: 4_200.00,
            at.F_PO_ISSUE_DATE: (_TODAY - timedelta(days=1)).isoformat(),
            at.F_SOURCE_MESSAGE_ID: "demo-review-3",
            at.F_IDEMPOTENCY: idempotency_key("demo-review-3", 0),
            at.F_PO_MATCH_METHOD: "fuzzy",
            at.F_PO_MATCH_SCORE: 0.71,
            at.F_NEEDS_REVIEW: True,
            at.F_REVIEW_REASON: (
                "Best candidate at 71%, below the 90% auto-apply bar. Two lots in "
                "this subdivision score within 4% of each other."
            ),
        }
    )

    # A PO that did match cleanly, so the queue is not the only PO on show.
    repo.create_purchase_order(
        {
            at.F_PO_NUMBER: "PO-10045",
            at.F_PO_AMOUNT: 12_500.00,
            at.F_PO_DEPOSIT: 6_250.00,
            at.F_PO_ISSUE_DATE: (_TODAY - timedelta(days=3)).isoformat(),
            at.F_SOURCE_MESSAGE_ID: "CAF7z1-po-003",
            at.F_IDEMPOTENCY: idempotency_key("CAF7z1-po-003", 0),
            at.F_PO_MATCH_METHOD: "exact_fingerprint",
            at.F_PO_MATCH_SCORE: 1.0,
            at.F_NEEDS_REVIEW: False,
        }
    )

    return repo


def seeded_repository() -> InMemoryRepository:
    return seed(InMemoryRepository())
