"""Purchase-order extraction from an email body and/or an attached PDF.

PDFs go to the model as a native `document` content block. No OCR dependency,
no pdftotext shell-out, no layout heuristics -- and it reads scanned POs, which
a text-extraction library cannot.
"""

from __future__ import annotations

import base64

from app.extraction.client import ExtractionResult, extract
from app.extraction.prompts import PO_EXTRACTION_SYSTEM
from app.extraction.schemas import ExtractedPurchaseOrder

# The Files API caps at 500MB but a request body caps at 32MB; a construction
# PO that exceeds even a few MB is a scan of something else.
MAX_PDF_BYTES = 20 * 1024 * 1024


class PdfTooLarge(ValueError):
    """Raised rather than silently truncating -- a half-read PO is worse than
    a rejected one, because it looks like it worked."""


def extract_purchase_order(
    *,
    subject: str | None = None,
    body: str | None = None,
    pdf_bytes: bytes | None = None,
) -> ExtractionResult:
    """Extract a PO from whichever of body/PDF is present.

    Both are passed when both exist: the covering email often names the
    property in plain language while the PDF carries the authoritative number
    and amount.
    """
    if not body and not pdf_bytes:
        raise ValueError("need at least one of body or pdf_bytes")

    content: list[dict] = []

    if pdf_bytes:
        if len(pdf_bytes) > MAX_PDF_BYTES:
            raise PdfTooLarge(
                f"PDF is {len(pdf_bytes) / 1e6:.1f}MB, limit is "
                f"{MAX_PDF_BYTES / 1e6:.0f}MB"
            )
        # The document block goes before the text block -- the model attends
        # to the document better when the instruction follows it.
        content.append(
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    # No newlines: the base64 payload must be a single string.
                    "data": base64.standard_b64encode(pdf_bytes).decode("ascii"),
                },
            }
        )

    if body:
        email_block = f"<email>\n<subject>{subject or ''}</subject>\n<body>\n{body}\n</body>\n</email>"
        content.append({"type": "text", "text": email_block})

    content.append(
        {
            "type": "text",
            "text": (
                "Extract the purchase order. If both a PDF and an email body "
                "are present and they disagree, the PDF is authoritative for "
                "the PO number and amount."
            ),
        }
    )

    return extract(
        system=PO_EXTRACTION_SYSTEM,
        content=content,
        output_format=ExtractedPurchaseOrder,
    )
