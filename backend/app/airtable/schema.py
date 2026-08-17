"""The Airtable base, defined as code.

Checked into git so the base is reproducible, reviewable in a pull request,
and rebuildable in a fresh workspace -- rather than existing only as clicks
somebody made once and cannot recall.

Two-pass by necessity: Airtable rejects a `multipleRecordLinks` field whose
target table does not exist yet, so every table is created with its scalar
fields first and the links are added afterwards. That also means the schema
tolerates circular references (Bids <-> Purchase Orders) which a single pass
could not express at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any

from app.pipeline import ORDERED_STAGES


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    options: dict[str, Any] | None = None
    description: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "type": self.type}
        if self.options is not None:
            payload["options"] = self.options
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class Link:
    """A link field added in pass two."""

    name: str
    to_table: str
    description: str | None = None
    prefers_single: bool = True


@dataclass(frozen=True)
class Table:
    name: str
    description: str
    fields: list[Field]
    links: list[Link] = dc_field(default_factory=list)


# --- reusable field shapes ---------------------------------------------

def _text(name: str, description: str | None = None) -> Field:
    return Field(name, "singleLineText", description=description)


def _long_text(name: str, description: str | None = None) -> Field:
    return Field(name, "multilineText", description=description)


def _currency(name: str, description: str | None = None) -> Field:
    return Field(
        name,
        "currency",
        options={"precision": 2, "symbol": "$"},
        description=description,
    )


def _date(name: str, description: str | None = None) -> Field:
    return Field(
        name,
        "date",
        options={"dateFormat": {"name": "iso"}},
        description=description,
    )


def _select(name: str, choices: list[str], description: str | None = None) -> Field:
    return Field(
        name,
        "singleSelect",
        options={"choices": [{"name": c} for c in choices]},
        description=description,
    )


def _checkbox(name: str, description: str | None = None) -> Field:
    return Field(
        name,
        "checkbox",
        options={"icon": "check", "color": "greenBright"},
        description=description,
    )


def _number(name: str, precision: int = 0, description: str | None = None) -> Field:
    return Field(
        name, "number", options={"precision": precision}, description=description
    )


# --- the base -----------------------------------------------------------

TABLES: list[Table] = [
    Table(
        name="Clients",
        description="General contractors and project managers who send bid requests.",
        fields=[
            _text("Name", "Project manager or primary contact."),
            _text("Company"),
            Field("Email", "email"),
            Field("Phone", "phoneNumber"),
            _long_text("Notes"),
        ],
    ),
    Table(
        name="Properties",
        description="Subdivisions, communities and standalone properties.",
        fields=[
            _text("Name", "Property or subdivision name as the client writes it."),
            _text("Address"),
            _text("City"),
            _text("State", "Two-letter code."),
        ],
        links=[Link("Client", "Clients")],
    ),
    Table(
        name="Bids",
        description=(
            "One record per property/lot. The spine of the system: a single "
            "bid-request email routinely produces several of these."
        ),
        fields=[
            _text("Bid Name", "Auto-composed as 'Property - Lot' for scanning."),
            _text("Lot / Unit", "Copied verbatim from the request."),
            _text("Address"),
            _text("City"),
            _text("State"),
            _long_text("Scope of Work"),
            _date("Bid Due Date"),
            _select(
                "Status",
                [stage.value for stage in ORDERED_STAGES],
                "The 14-stage pipeline, plus Lost and Cancelled.",
            ),
            _text("Estimator", "Who is assigned to price it."),
            _currency("Bid Amount"),
            # --- machinery ---
            _text(
                "Job Fingerprint",
                "Deterministic hash of property+lot. How revisions find their "
                "original instead of creating a duplicate.",
            ),
            _text(
                "Idempotency Key",
                "Per (email, record). Makes a Zapier retry a no-op.",
            ),
            _text("Source Message ID", "Gmail message id of the originating email."),
            Field("Source Email Link", "url", description="Deep link back to the thread."),
            _number(
                "Extraction Confidence",
                precision=2,
                description="0-1, as reported by the extraction model.",
            ),
            _checkbox("Needs Review", "Blocked awaiting a human decision."),
            _long_text("Review Reason"),
        ],
        links=[
            Link("Property", "Properties"),
            Link("Client", "Clients"),
            Link("Assigned Crew", "Crews"),
        ],
    ),
    Table(
        name="Purchase Orders",
        description="POs received by email or PDF, matched back to an existing bid.",
        fields=[
            _text("PO Number"),
            _currency("Approved Amount"),
            _currency(
                "Deposit Amount",
                "50% of the approved amount, computed on ingest.",
            ),
            _date("Issue Date"),
            _text("Source Message ID"),
            _text("Idempotency Key"),
            _select(
                "Match Method",
                ["exact_fingerprint", "fuzzy", "llm_adjudicated", "no_match"],
                "Which tier of the matcher resolved this PO.",
            ),
            _number("Match Score", precision=2),
            _checkbox("Needs Review"),
            _long_text("Review Reason"),
        ],
        links=[Link("Bid", "Bids")],
    ),
    Table(
        name="Invoices",
        description=(
            "Deposit and final invoices. Created in Joist by hand -- see "
            "docs/joist-assessment.md -- and tracked here."
        ),
        fields=[
            _text("Invoice Number"),
            _select("Type", ["Deposit", "Final", "Change Order"]),
            _currency("Amount"),
            _select("Status", ["Needed", "Sent", "Paid", "Void"]),
            _date("Sent Date"),
            _text(
                "QuickBooks Reference",
                "Joist syncs natively to QuickBooks Online; this is the seam we "
                "read payment status back through.",
            ),
        ],
        links=[Link("Bid", "Bids")],
    ),
    Table(
        name="Payments",
        description="Payments received against invoices.",
        fields=[
            _text("Reference"),
            _currency("Amount"),
            _date("Received Date"),
            _select("Method", ["Check", "ACH", "Card", "Cash", "Other"]),
        ],
        links=[Link("Invoice", "Invoices")],
    ),
    Table(
        name="Crews",
        description="Crew roster available for assignment.",
        fields=[
            _text("Crew Name"),
            _text("Lead"),
            Field("Phone", "phoneNumber"),
            _checkbox("Active"),
        ],
    ),
    Table(
        name="Material Orders",
        description="Materials ordered per job.",
        fields=[
            _text("Order Reference"),
            _text("Supplier"),
            _long_text("Items"),
            _date("Ordered Date"),
            _date("Expected Delivery"),
            _select("Status", ["Needed", "Ordered", "Delivered", "Backordered"]),
        ],
        links=[Link("Bid", "Bids")],
    ),
    Table(
        name="Run Log",
        description=(
            "Append-only audit trail. Every extraction, match and decision, "
            "with what it cost. This is what makes the system's behaviour "
            "checkable rather than something you take on trust."
        ),
        fields=[
            _text("Event", "e.g. bid_extracted, po_matched, revision_applied."),
            Field(
                "Timestamp",
                "dateTime",
                options={
                    "dateFormat": {"name": "iso"},
                    "timeFormat": {"name": "24hour"},
                    "timeZone": "utc",
                },
            ),
            _text("Source Message ID"),
            _select(
                "Decision",
                ["create", "update", "no_op", "cancel", "review", "match", "error"],
            ),
            _long_text("Reason"),
            _long_text(
                "Changed Fields",
                "Previous values, captured before an update is applied. This is "
                "what makes a revision reversible.",
            ),
            _text("Model"),
            _number("Input Tokens"),
            _number("Output Tokens"),
            Field(
                "Cost USD",
                "number",
                options={"precision": 6},
                description="Derived from published list pricing.",
            ),
            _number("Confidence", precision=2),
            _long_text("Raw Payload", "The inbound webhook body, for replay."),
        ],
        links=[Link("Bid", "Bids")],
    ),
]

TABLES_BY_NAME: dict[str, Table] = {t.name: t for t in TABLES}
