#!/usr/bin/env python3
"""Post a fixture at the running service, correctly signed.

The demo driver, and the manual half of the verification checklist.

    python scripts/send_fixture.py multi_lot_bid_request.json
    python scripts/send_fixture.py multi_lot_bid_request.json   # again: no-op
    python scripts/send_fixture.py purchase_order_email.json --pdf tests/fixtures/po_sample.pdf

Signs with WEBHOOK_SECRET exactly the way the Zapier Code step does, so a green
run here means the Zap will work too.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.security import SIGNATURE_HEADER, sign  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", help="file name under tests/fixtures/")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--pdf", type=Path, help="attach a PDF (PO endpoint only)")
    parser.add_argument(
        "--endpoint",
        choices=["bid-request", "purchase-order"],
        help="defaults to purchase-order when the fixture name mentions a PO",
    )
    args = parser.parse_args()

    path = FIXTURES / args.fixture if not Path(args.fixture).exists() else Path(args.fixture)
    if not path.exists():
        print(f"no such fixture: {path}", file=sys.stderr)
        return 2

    payload = json.loads(path.read_text())

    endpoint = args.endpoint or (
        "purchase-order"
        if "purchase_order" in path.name or "po_" in path.name
        else "bid-request"
    )

    if args.pdf:
        payload["pdf_base64"] = base64.b64encode(args.pdf.read_bytes()).decode("ascii")

    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}

    secret = get_settings().webhook_secret
    if secret:
        headers[SIGNATURE_HEADER] = sign(body, secret)
    else:
        print(
            "! WEBHOOK_SECRET unset -- sending unsigned. The service will "
            "reject this unless ALLOW_UNSIGNED_WEBHOOKS=true.",
            file=sys.stderr,
        )

    url = f"{args.base_url.rstrip('/')}/webhooks/{endpoint}"
    print(f"POST {url}  ({len(body)} bytes)")

    try:
        response = httpx.post(url, content=body, headers=headers, timeout=180.0)
    except httpx.HTTPError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(f"<- {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
