# Joist: what can and cannot be automated

You asked for an evaluation rather than a promise. This is it, including the
part that is a straight no.

**Assessed August 2026.** If Joist ships a public API later, the recommendation
in here changes and should be revisited.

---

## The short version

| Step | Automated? | How |
|---|---|---|
| PO received → office alerted a deposit invoice is due | **Yes** | Airtable status change fires a Zap |
| Deposit amount calculated (50% of approved) | **Yes** | Computed on PO ingest, shown in the alert |
| Which job, which customer, which PO number | **Yes** | Already matched to the bid before the alert fires |
| **Convert the Joist estimate to an invoice and send it** | **No** | Manual click in Joist. See below. |
| Mark "invoice sent" in Airtable | **Partly** | One click from the alert, or read back via QuickBooks |
| Deposit paid → Airtable status updated | **Yes** | Via QuickBooks Online, not via Joist |
| Final invoice and payment | **Same shape** as the deposit |

One manual step remains, and it is the invoicing click itself. Everything on
either side of it is automated.

---

## Why the invoicing step cannot be automated

**Joist publishes no API.** There is no developer portal, no REST
documentation, and no OAuth application registration. Nothing exists to
integrate against.

**Joist has no Zapier app.** Zapier's own community confirms one has never been
built. Zapier apps are built by the vendor, so this is not something a
consultant can work around — the connector would have to come from Joist.

Sources, so you can check rather than take my word for it:

- Supergood, *Joist API* — <https://supergood.ai/docs/joist-api> — describes
  Joist as exposing "no documented REST API or developer portal".
- Zapier Community, *Joist App* — <https://community.zapier.com/how-do-i-3/joist-app-7958>
  — confirms no Zap app is available and directs requests to the vendor.

### The workaround I am not proposing

A third-party service (Supergood) offers an unofficial Joist API by driving
Joist's authenticated web session — effectively logging in as you and
scripting the interface. It would technically let us create invoices
programmatically.

**I recommend against it, and I would say the same if a competitor proposed
it.** Three reasons:

1. **It breaks without warning.** It depends on Joist's internal endpoints and
   page structure. Any redesign on their side stops your invoicing, with no
   deprecation notice, because there is no contract to deprecate.
2. **It sits outside Joist's terms.** Automating an authenticated session you
   were granted for interactive use is not something Joist has sanctioned. That
   is a poor foundation for the system that issues your invoices.
3. **It needs your Joist credentials** to be held by a third party in order to
   act as you.

The failure mode matters more than the probability: it fails at the exact point
where money leaves the system, and it fails silently.

---

## What we do instead: QuickBooks Online

Joist syncs natively to QuickBooks Online — that is Joist's own supported
integration, and it is the seam that actually exists. QuickBooks has a
documented API *and* a maintained Zapier app.

So the loop closes through your accounting system rather than through scraping:

```
PO received (Airtable)
      │
      ├─▶ Zap: alert the office — "Lot 42, deposit $6,250, PO 10045"
      │
      ▼
  Office converts the estimate in Joist and sends it     ← the manual click
      │
      ▼
  Joist ──native sync──▶ QuickBooks Online
                               │
                               ▼
                    Zap: payment recorded in QBO
                               │
                               ▼
              Airtable status → "Deposit Paid"
```

This is better than scraping Joist even setting the terms question aside:
QuickBooks is the system you reconcile against, so a payment recorded there is
the version your accountant already treats as authoritative.

---

## What the manual step actually costs

The click stays. What goes away is the work around it — and that is where the
time actually goes:

- Noticing a PO arrived at all
- Finding which estimate it corresponds to
- Working out 50% of the approved amount
- Remembering to chase whether the deposit was ever paid
- Discovering three days later that the invoice was never sent

The alert names the customer, the job, the PO number and the deposit figure.
The office opens Joist already knowing exactly what to do.

*No estimate of hours saved is given here because none has been measured. Once
this runs against real mail for a fortnight, the run log will tell you the real
number rather than my guess at it.*

---

## If you want to remove the manual step entirely

Two honest options, neither of which I would push on you:

1. **Move invoicing to QuickBooks Online.** You already sync to it. QBO can
   raise and send the invoice directly, which is fully automatable through a
   supported API. The cost is that estimating stays in Joist while invoicing
   moves, which splits a workflow your team knows.
2. **Ask Joist for API access.** Vendors sometimes have unpublished partner
   programmes. Costs nothing to ask, and if it exists, this recommendation
   changes.

I would not switch invoicing platforms on the strength of one click. But you
should know the option is there, and what it would buy.
