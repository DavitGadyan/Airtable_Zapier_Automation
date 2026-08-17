"""The bid lifecycle.

Single source of truth for the 14 stages, taken verbatim from how the client
described their own process. Imported by the Airtable schema (to build the
single-select), by revision handling (to know what is safe to overwrite), and
by the dashboard (to lay out the board).

Keeping this in one place is what stops the Airtable select options and the
application's notion of "late stage" drifting apart -- which is the kind of
drift nobody notices until a closed job gets silently reopened.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import Enum


class Stage(str, Enum):
    BID_REQUEST = "Bid Request"
    BID_ASSIGNED = "Bid Assigned"
    BID_SUBMITTED = "Bid Submitted"
    PO_RECEIVED = "PO Received"
    DEPOSIT_INVOICE_SENT = "Deposit Invoice Sent"
    DEPOSIT_PAID = "Deposit Paid"
    CREW_ASSIGNED = "Crew Assigned"
    MATERIALS_ORDERED = "Materials Ordered"
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    FINAL_INVOICE_SENT = "Final Invoice Sent"
    FINAL_PAYMENT_RECEIVED = "Final Payment Received"
    CLOSED = "Closed"

    # Outcomes that sit outside the linear flow. Cancelled is a status, never
    # a deletion -- see app/matching/revision.py.
    LOST = "Lost"
    CANCELLED = "Cancelled"


#: In pipeline order, for the board and the single-select.
ORDERED_STAGES: list[Stage] = [
    Stage.BID_REQUEST,
    Stage.BID_ASSIGNED,
    Stage.BID_SUBMITTED,
    Stage.PO_RECEIVED,
    Stage.DEPOSIT_INVOICE_SENT,
    Stage.DEPOSIT_PAID,
    Stage.CREW_ASSIGNED,
    Stage.MATERIALS_ORDERED,
    Stage.SCHEDULED,
    Stage.IN_PROGRESS,
    Stage.COMPLETED,
    Stage.FINAL_INVOICE_SENT,
    Stage.FINAL_PAYMENT_RECEIVED,
    Stage.CLOSED,
    Stage.LOST,
    Stage.CANCELLED,
]

#: Money has moved or work has started. A revision arriving against one of
#: these is not a routine edit -- it needs a human, because the estimate it
#: would rewrite has already been acted on.
COMMITTED_STAGES: frozenset[Stage] = frozenset(
    {
        Stage.PO_RECEIVED,
        Stage.DEPOSIT_INVOICE_SENT,
        Stage.DEPOSIT_PAID,
        Stage.CREW_ASSIGNED,
        Stage.MATERIALS_ORDERED,
        Stage.SCHEDULED,
        Stage.IN_PROGRESS,
        Stage.COMPLETED,
        Stage.FINAL_INVOICE_SENT,
        Stage.FINAL_PAYMENT_RECEIVED,
    }
)

#: Nothing further should happen automatically to a bid in one of these.
TERMINAL_STAGES: frozenset[Stage] = frozenset(
    {Stage.CLOSED, Stage.LOST, Stage.CANCELLED}
)


def is_committed(stage: str | Stage | None) -> bool:
    """True once a PO has landed -- i.e. once real money is attached."""
    if stage is None:
        return False
    try:
        return Stage(stage) in COMMITTED_STAGES
    except ValueError:
        return False


def is_terminal(stage: str | Stage | None) -> bool:
    if stage is None:
        return False
    try:
        return Stage(stage) in TERMINAL_STAGES
    except ValueError:
        return False


def deposit_amount(approved_amount: float, fraction: float = 0.50) -> float:
    """The client's standing 50% deposit rule, rounded to cents.

    Decimal with ROUND_HALF_UP rather than round(): this figure goes onto an
    invoice the client sends to a customer. Binary floats cannot represent
    4999.995 exactly and round() applies banker's rounding on top, so the
    obvious one-liner quietly bills a cent less than half on some amounts.
    """
    cents = (Decimal(str(approved_amount)) * Decimal(str(fraction))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return float(cents)
