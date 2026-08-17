#!/usr/bin/env python3
"""Generate a sample purchase-order PDF for demos and live testing.

Kept as a generator rather than a committed binary so the fixture is
reviewable in a diff and easy to vary -- change the lot, run it again, and see
whether matching still lands.

    python scripts/make_po_pdf.py                       # default PO
    python scripts/make_po_pdf.py --lot 43 --amount 9800

Needs the dev extra: pip install -e ".[dev]"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "po_sample.pdf"


def build(path: Path, *, po_number: str, prop: str, lot: str, amount: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=LETTER)
    width, height = LETTER
    y = height - 1.0 * inch

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(1 * inch, y, "PURCHASE ORDER")

    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 1 * inch, y, "Copperline Homes")
    y -= 0.28 * inch
    pdf.drawRightString(width - 1 * inch, y, "1400 Ustick Rd, Boise, ID 83704")

    y -= 0.6 * inch
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(1 * inch, y, f"PO Number: {po_number}")
    pdf.setFont("Helvetica", 11)
    y -= 0.3 * inch
    pdf.drawString(1 * inch, y, "Issue Date: 2026-08-18")
    y -= 0.3 * inch
    pdf.drawString(1 * inch, y, f"Property: {prop}")
    y -= 0.3 * inch
    pdf.drawString(1 * inch, y, f"Lot / Unit: {lot}")
    y -= 0.3 * inch
    pdf.drawString(1 * inch, y, "Vendor: (your company)")

    y -= 0.55 * inch
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(1 * inch, y, "Scope of Work")
    pdf.setFont("Helvetica", 10)
    for line in (
        "Remove and replace carpet and pad throughout.",
        "Luxury vinyl plank to both bathrooms.",
        "Includes haul-away and disposal of existing material.",
    ):
        y -= 0.26 * inch
        pdf.drawString(1.15 * inch, y, f"- {line}")

    # A subtotal deliberately sits above the total: the prompt tells the model
    # to take the approved contract value, and this is what tests that.
    y -= 0.55 * inch
    pdf.setFont("Helvetica", 11)
    pdf.drawRightString(width - 2.2 * inch, y, "Materials subtotal:")
    pdf.drawRightString(width - 1 * inch, y, f"${amount * 0.62:,.2f}")
    y -= 0.28 * inch
    pdf.drawRightString(width - 2.2 * inch, y, "Labor subtotal:")
    pdf.drawRightString(width - 1 * inch, y, f"${amount * 0.38:,.2f}")
    y -= 0.34 * inch
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(width - 2.2 * inch, y, "TOTAL APPROVED:")
    pdf.drawRightString(width - 1 * inch, y, f"${amount:,.2f}")

    y -= 0.7 * inch
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(
        1 * inch, y, "Terms: 50% deposit invoice required prior to scheduling."
    )

    pdf.showPage()
    pdf.save()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--po-number", default="10045")
    parser.add_argument("--property", dest="prop", default="Willow Creek Phase 2")
    parser.add_argument("--lot", default="Lot 42")
    parser.add_argument("--amount", type=float, default=12_500.00)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    path = build(
        args.out,
        po_number=args.po_number,
        prop=args.prop,
        lot=args.lot,
        amount=args.amount,
    )
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
