# Upwork proposal — draft

Trim to taste. The two things doing the work here are the Joist finding in the
opening line and the fact that the duplicate-safety logic already exists and
is tested.

---

Hi — before anything else, one finding that affects your scope.

**Joist has no public API and no Zapier app.** I checked rather than assumed:
there is no developer portal or REST documentation, and Zapier's own community
confirms no connector exists. There *is* an unofficial reverse-engineered
service that drives Joist's login session, and I would not build your invoicing
on it — it breaks whenever Joist ships a UI change and it sits outside their
terms.

What does exist is the seam Joist itself supports: it syncs natively to
QuickBooks Online, which has a real API and a maintained Zapier app. So the
plan is to automate everything on both sides of the one manual click — the
alert that a deposit invoice is due, with the customer, the job, the PO number
and the 50% figure already calculated, and then the payment status read back
through QuickBooks. Converting the estimate in Joist stays a click. I would
rather tell you that now than in week three.

**I've already built the hard parts.** Not a mockup — a working service with a
test suite:

- **One email becomes six records.** Your multi-lot requests are split into
  separate bids, each with its own address, scope and due date. This is the
  piece no rule-based tool does reliably, and it is the most expensive thing
  your team currently does by hand.
- **Revisions and cancellations, safely.** You asked for changes handled
  "without creating duplicates or accidentally deleting valid bids". A stable
  fingerprint of property and lot survives a scope change, so a revision finds
  and updates the original instead of creating a second row. Previous values
  are written to an audit log *before* the update lands, so every change is
  reversible. **No code path in the system deletes a bid.** A cancellation sets
  a status, keeps the record, and waits for one click — I've left automatic
  cancellation switched off deliberately, because a misread one stands a crew
  down on a live job and nobody notices an absence.
- **POs match existing bids rather than creating duplicate jobs.** Three tiers:
  exact key, then fuzzy matching so "Willow Crk" still finds Willow Creek, and
  the AI only for genuinely ambiguous cases. Two lots in one subdivision
  scoring nearly the same never auto-applies — it goes to a human.

**Cost.** About four cents per bid email in AI spend, from published Claude
pricing — the arithmetic is on the architecture page and every call is logged
with its token count, so you can verify it from your own Airtable base rather
than taking my word for it.

**What you'd get:** the Airtable base (9 tables, defined as code so it is
reproducible), the extraction service, four Zaps documented step by step so
your team can maintain them, the review queue, and the Joist assessment above
written up with sources.

I've also built an interactive walkthrough of the architecture — every
component explains what it does, why it exists, and what it costs, including
the parts I chose not to automate. Happy to screen-share it; it takes about
eight minutes and you'll know exactly what you're buying.

One question: roughly how many bid-request emails come in per week, and how
many lots does a typical one cover? That drives the running cost, and I'd
rather quote you a real number than a range.

---

## Notes for you, not the client

- Record the guided tour (24 stops, ~8 minutes) and attach it, or share the
  deployed `/architecture` link. That is the differentiator against 50 text
  proposals.
- Lead with Joist in the first line. Most competing proposals will promise a
  Joist integration that cannot exist, and the client will find out later.
- Don't quote hours-saved figures. You have no measured baseline, and the
  client can disprove a made-up one — which would discredit the four-cent
  figure too, and that one is real.
- The demo sequence that lands best: post the six-lot fixture, show six
  records, post it again, show nothing happens.
