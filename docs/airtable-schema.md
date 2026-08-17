# Airtable base schema

Generated from `backend/app/airtable/schema.py` -- the source of truth.
Regenerate with `python scripts/provision_airtable.py --emit-doc`.

Build these by hand only if the API token cannot write schema. Create
all tables and their plain fields first, then add the link fields at
the end -- Airtable will not accept a link to a table that does not
exist yet.

## Clients

General contractors and project managers who send bid requests.

| Field | Type | Notes |
|---|---|---|
| Name | `singleLineText` | Project manager or primary contact. |
| Company | `singleLineText` |  |
| Email | `email` |  |
| Phone | `phoneNumber` |  |
| Notes | `multilineText` |  |

## Properties

Subdivisions, communities and standalone properties.

| Field | Type | Notes |
|---|---|---|
| Name | `singleLineText` | Property or subdivision name as the client writes it. |
| Address | `singleLineText` |  |
| City | `singleLineText` |  |
| State | `singleLineText` | Two-letter code. |
| Client | `link` | Links to **Clients**. |

## Bids

One record per property/lot. The spine of the system: a single bid-request email routinely produces several of these.

| Field | Type | Notes |
|---|---|---|
| Bid Name | `singleLineText` | Auto-composed as 'Property - Lot' for scanning. |
| Lot / Unit | `singleLineText` | Copied verbatim from the request. |
| Address | `singleLineText` |  |
| City | `singleLineText` |  |
| State | `singleLineText` |  |
| Scope of Work | `multilineText` |  |
| Bid Due Date | `date` |  |
| Status | `singleSelect` | The 14-stage pipeline, plus Lost and Cancelled. Options: Bid Request, Bid Assigned, Bid Submitted, PO Received, Deposit Invoice Sent, Deposit Paid, Crew Assigned, Materials Ordered, Scheduled, In Progress, Completed, Final Invoice Sent, Final Payment Received, Closed, Lost, Cancelled |
| Estimator | `singleLineText` | Who is assigned to price it. |
| Bid Amount | `currency` |  |
| Job Fingerprint | `singleLineText` | Deterministic hash of property+lot. How revisions find their original instead of creating a duplicate. |
| Idempotency Key | `singleLineText` | Per (email, record). Makes a Zapier retry a no-op. |
| Source Message ID | `singleLineText` | Gmail message id of the originating email. |
| Source Email Link | `url` | Deep link back to the thread. |
| Extraction Confidence | `number` | 0-1, as reported by the extraction model. |
| Needs Review | `checkbox` | Blocked awaiting a human decision. |
| Review Reason | `multilineText` |  |
| Property | `link` | Links to **Properties**. |
| Client | `link` | Links to **Clients**. |
| Assigned Crew | `link` | Links to **Crews**. |

## Purchase Orders

POs received by email or PDF, matched back to an existing bid.

| Field | Type | Notes |
|---|---|---|
| PO Number | `singleLineText` |  |
| Approved Amount | `currency` |  |
| Deposit Amount | `currency` | 50% of the approved amount, computed on ingest. |
| Issue Date | `date` |  |
| Source Message ID | `singleLineText` |  |
| Idempotency Key | `singleLineText` |  |
| Match Method | `singleSelect` | Which tier of the matcher resolved this PO. Options: exact_fingerprint, fuzzy, llm_adjudicated, no_match |
| Match Score | `number` |  |
| Needs Review | `checkbox` |  |
| Review Reason | `multilineText` |  |
| Bid | `link` | Links to **Bids**. |

## Invoices

Deposit and final invoices. Created in Joist by hand -- see docs/joist-assessment.md -- and tracked here.

| Field | Type | Notes |
|---|---|---|
| Invoice Number | `singleLineText` |  |
| Type | `singleSelect` | Options: Deposit, Final, Change Order |
| Amount | `currency` |  |
| Status | `singleSelect` | Options: Needed, Sent, Paid, Void |
| Sent Date | `date` |  |
| QuickBooks Reference | `singleLineText` | Joist syncs natively to QuickBooks Online; this is the seam we read payment status back through. |
| Bid | `link` | Links to **Bids**. |

## Payments

Payments received against invoices.

| Field | Type | Notes |
|---|---|---|
| Reference | `singleLineText` |  |
| Amount | `currency` |  |
| Received Date | `date` |  |
| Method | `singleSelect` | Options: Check, ACH, Card, Cash, Other |
| Invoice | `link` | Links to **Invoices**. |

## Crews

Crew roster available for assignment.

| Field | Type | Notes |
|---|---|---|
| Crew Name | `singleLineText` |  |
| Lead | `singleLineText` |  |
| Phone | `phoneNumber` |  |
| Active | `checkbox` |  |

## Material Orders

Materials ordered per job.

| Field | Type | Notes |
|---|---|---|
| Order Reference | `singleLineText` |  |
| Supplier | `singleLineText` |  |
| Items | `multilineText` |  |
| Ordered Date | `date` |  |
| Expected Delivery | `date` |  |
| Status | `singleSelect` | Options: Needed, Ordered, Delivered, Backordered |
| Bid | `link` | Links to **Bids**. |

## Run Log

Append-only audit trail. Every extraction, match and decision, with what it cost. This is what makes the system's behaviour checkable rather than something you take on trust.

| Field | Type | Notes |
|---|---|---|
| Event | `singleLineText` | e.g. bid_extracted, po_matched, revision_applied. |
| Timestamp | `dateTime` |  |
| Source Message ID | `singleLineText` |  |
| Decision | `singleSelect` | Options: create, update, no_op, cancel, review, match, error |
| Reason | `multilineText` |  |
| Changed Fields | `multilineText` | Previous values, captured before an update is applied. This is what makes a revision reversible. |
| Model | `singleLineText` |  |
| Input Tokens | `number` |  |
| Output Tokens | `number` |  |
| Cost USD | `number` | Derived from published list pricing. |
| Confidence | `number` |  |
| Raw Payload | `multilineText` | The inbound webhook body, for replay. |
| Bid | `link` | Links to **Bids**. |
