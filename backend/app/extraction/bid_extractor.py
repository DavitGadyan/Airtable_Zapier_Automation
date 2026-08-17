"""Bid-request email -> N structured bid records.

The one-email-to-many-records step. Everything downstream depends on the split
being right, which is why the prompt spends most of its words on it.
"""

from __future__ import annotations

from app.extraction.client import ExtractionResult, extract
from app.extraction.prompts import BID_EXTRACTION_SYSTEM
from app.extraction.schemas import BidRequestBatch


def build_email_document(
    *, subject: str, body: str, sender: str | None = None, received_at: str | None = None
) -> str:
    """Render an email into the block handed to the model.

    Tagged rather than concatenated so the model can tell a subject line from
    a quoted reply chain -- headers and body routinely contain conflicting
    property names, and which one wins depends on knowing which is which.
    """
    parts = ["<email>"]
    if sender:
        parts.append(f"<from>{sender}</from>")
    if received_at:
        parts.append(f"<received>{received_at}</received>")
    parts.append(f"<subject>{subject}</subject>")
    parts.append(f"<body>\n{body}\n</body>")
    parts.append("</email>")
    return "\n".join(parts)


def extract_bids(
    *,
    subject: str,
    body: str,
    sender: str | None = None,
    received_at: str | None = None,
) -> ExtractionResult:
    """Extract every distinct bid request from one email."""
    document = build_email_document(
        subject=subject, body=body, sender=sender, received_at=received_at
    )
    return extract(
        system=BID_EXTRACTION_SYSTEM,
        content=[
            {"type": "text", "text": document},
            {
                "type": "text",
                "text": (
                    "Extract every distinct property/lot in this email as its "
                    "own entry."
                ),
            },
        ],
        output_format=BidRequestBatch,
    )
