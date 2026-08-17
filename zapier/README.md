# Zapier build guide

Four Zaps. Between them they cover every trigger and notification in the
system; the FastAPI service handles only extraction, matching and revision
logic.

The division is deliberate: **Zapier holds what should be editable, code holds
what must be correct.** Anything you might reasonably want to change — who gets
notified, which label is watched, what an alert says — lives here, where you
can change it without a developer and without a deploy.

Prerequisites: the service reachable on a public HTTPS URL, and the
`WEBHOOK_SECRET` from `backend/.env` to hand.

---

## Z1 · Bid request intake

| | |
|---|---|
| **Trigger** | Gmail → *New Labeled Email* |
| **Label** | `Bids/Incoming` |
| **Action 1** | Code by Zapier (see below) — signs the payload |
| **Action 2** | Webhooks by Zapier → *Custom Request* |

**Action 1 — Code by Zapier (JavaScript).** Zapier cannot compute an HMAC in a
plain webhook step, so a Code step builds both the body and its signature. Set
`SECRET` as an input value, not inline, so it is not visible in the Zap history.

```js
const crypto = require("crypto");

const payload = {
  message_id: inputData.messageId,
  subject: inputData.subject || "",
  body: inputData.bodyPlain || "",
  sender: inputData.from || null,
  received_at: inputData.date || null,
  email_link: inputData.messageUrl || null,
};

// Sign the exact bytes that get sent. Re-serialising downstream would change
// them and the signature would no longer match.
const raw = JSON.stringify(payload);
const signature = crypto
  .createHmac("sha256", inputData.SECRET)
  .update(raw)
  .digest("hex");

output = [{ raw, signature }];
```

Input fields: `messageId`, `subject`, `bodyPlain`, `from`, `date`, `messageUrl`
mapped from the Gmail trigger, plus `SECRET`.

**Action 2 — Webhooks by Zapier → Custom Request**

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `https://<your-host>/webhooks/bid-request` |
| Data Pass-Through? | **No** |
| Data | `{{raw}}` — the Code step's output, verbatim |
| Headers | `Content-Type: application/json`, `X-Signature: {{signature}}` |

> **The one thing that will bite you.** Send the Code step's `raw` string as the
> body. If you rebuild the JSON from individual fields in the webhook step,
> Zapier will re-serialise it — different key order or spacing — and the
> signature check will fail with a 401 that looks like a wrong secret.

**Response.** `{"created": 6, "flagged_for_review": 0, "cost_usd": 0.034, ...}`.
Re-running the same email returns `{"skipped": 1}` and creates nothing.

---

## Z2 · Purchase order intake

| | |
|---|---|
| **Trigger** | Gmail → *New Labeled Email* |
| **Label** | `POs/Incoming` |
| **Actions** | Same Code + Webhooks pair, posting to `/webhooks/purchase-order` |

Payload differs only in the attachment fields:

```js
const payload = {
  message_id: inputData.messageId,
  subject: inputData.subject || "",
  body: inputData.bodyPlain || "",
  pdf_url: inputData.attachmentUrl || null,   // Zapier's attachment link
};
```

The service fetches `pdf_url` itself. If a PDF is present it is treated as
authoritative for the PO number and amount, with the email body used as
supporting context.

**On failure.** A non-2xx makes Zapier retry, which is safe — the idempotency
key means a retry creates nothing. A `502` means the attachment URL expired;
Zapier's links are short-lived, so avoid long delays before this step.

---

## Z3 · Deposit invoice needed

The alert that closes the gap around Joist's manual step.

| | |
|---|---|
| **Trigger** | Airtable → *New or Updated Record* in **Bids** |
| **Trigger field** | `Status` |
| **Filter** | `Status` exactly matches `PO Received` **and** `Needs Review` is false |
| **Action** | Slack / Email / SMS — whichever the office actually reads |

Message template:

```
Deposit invoice needed — {{Bid Name}}

PO:        {{Purchase Orders Bid PO Number}}
Approved:  {{Purchase Orders Bid Approved Amount}}
Deposit:   {{Purchase Orders Bid Deposit Amount}}   (50%)
Client:    {{Client Name}}

Raise it in Joist, then set Status to "Deposit Invoice Sent".
```

> The `Needs Review is false` filter matters. Without it, a PO the system
> flagged as uncertain would still trigger an invoice request — which is
> exactly the safety rule the confidence gate exists to enforce, undone in the
> last step.

---

## Z4 · Deposit paid (via QuickBooks)

Joist has no API. It does sync natively to QuickBooks Online, which has both.
See `docs/joist-assessment.md` for why this is the right seam.

| | |
|---|---|
| **Trigger** | QuickBooks Online → *New Payment* |
| **Action 1** | Airtable → *Find Record* in **Invoices**, matching `QuickBooks Reference` |
| **Action 2** | Airtable → *Update Record* on the linked **Bid** |

Set `Status` to `Deposit Paid` (or `Final Payment Received`, depending on the
invoice's `Type`). Enable *"Continue only if the search succeeded"* on Action 1
— a payment for something outside this system should be ignored, not written
against the wrong job.

---

## Testing before you go live

1. Point the URLs at a local service via an HTTPS tunnel.
2. Send yourself a real multi-lot request and label it. Check Airtable has one
   record per lot.
3. **Send the identical email again.** Nothing new should appear. This is the
   duplicate protection, and it is worth watching once with your own eyes.
4. Break the signature deliberately — change one character of `SECRET` in the
   Code step — and confirm you get a `401`. Then put it back.

`backend/scripts/send_fixture.py` signs payloads exactly the way the Code step
above does, so a green run there means the Zap will work too.

---

## Task volume

Roughly two Zapier tasks per bid email and per PO, plus one per alert and one
per payment. Your plan's task allowance is the thing to size against; the
service call itself is a single task regardless of how many lots come out of
the email, because splitting happens inside the service rather than by looping
in Zapier.
