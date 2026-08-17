/**
 * The architecture graph's content.
 *
 * Structured as the pipeline a bid request actually travels, from the project
 * manager's email through to a closed job. Each stage expands into its parts,
 * so a viewer meets eight boxes and drills into whichever matters to them.
 *
 * Every node answers four questions -- what it does, why it exists, what it
 * saves the buyer, what the user feels -- because a diagram of boxes and
 * arrows explains nothing to the person deciding whether to pay for it.
 *
 * ON NUMBERS. Every figure here is one of three things, and which one is
 * always stated:
 *   (a) published vendor pricing  -- Claude API list rates
 *   (b) derived from (a), with the arithmetic shown in the caption
 *   (c) an estimate -- tagged `estimated: true`, always
 * Nothing about this client's current volumes or hours has been measured, so
 * every operational figure is (c). One number a client checks and disproves
 * discredits every other number on the page.
 *
 * Deliberately static. This page renders with the backend stopped, which is
 * the point: a demo must never fail because a service is cold.
 */

import type { IconKey } from "@/lib/node-icons";

// ---------------------------------------------------------------------------
// Tiers -- one per top-level stage.
// ---------------------------------------------------------------------------

export type TierId =
  | "client"
  | "ui"
  | "gateway"
  | "context"
  | "engine"
  | "data"
  | "ops"
  | "platform";

export interface Tier {
  id: TierId;
  label: string;
  blurb: string;
  color: string;
}

export const TIERS: Tier[] = [
  { id: "client", label: "Project Manager", blurb: "Where the work starts", color: "#8d99a4" },
  { id: "ui", label: "Inbox & Dashboard", blurb: "What people touch", color: "#3f7a75" },
  { id: "gateway", label: "Ingestion", blurb: "How mail gets in, exactly once", color: "#a9661b" },
  { id: "context", label: "Document Assembly", blurb: "What the model is given", color: "#7a6ba8" },
  // The accent. This is the stage the commercial argument rests on.
  { id: "engine", label: "Extraction & Matching", blurb: "The part you are paying for", color: "#c8821f" },
  { id: "data", label: "Airtable", blurb: "Where the truth lives", color: "#5b7596" },
  { id: "ops", label: "Audit & Review", blurb: "Proof it works", color: "#b04e72" },
  { id: "platform", label: "Platform & Joist", blurb: "How it runs and what it doesn't touch", color: "#6b7280" },
];

// ---------------------------------------------------------------------------
// Nodes
// ---------------------------------------------------------------------------

export interface ArchNode {
  id: string;
  label: string;
  tier: TierId;
  parent?: string;
  flowOrder?: number;
  sub?: string;
  logo?: string;
  icon?: IconKey;
  size?: number;

  what: string;
  whyUsed: string;
  clientBenefit: string;
  userBenefit: string;
  metric?: { value: string; caption: string; estimated?: boolean };
  demoNote: string;
}

/** Logical parent only -- deliberately has no node. */
export const ROOT_ID = "root";

export const NODES: ArchNode[] = [
  // ================================================= 0. the project manager
  {
    id: "pm",
    label: "Project Manager",
    tier: "client",
    parent: ROOT_ID,
    flowOrder: 0,
    sub: "emails six lots at once",
    icon: "user",
    size: 8,
    what:
      "A builder's project manager emails a bid request. One email routinely covers six lots across a subdivision, each with its own address and its own slightly different scope.",
    whyUsed:
      "This is the entry point, and the shape of it is the whole problem. Every lot becomes a separate job that is bid, won, scheduled and invoiced independently — so one email has to become six records. Today somebody reads it and types them in.",
    clientBenefit:
      "Every one of those emails is currently manual data entry that happens before anyone can quote. The lots that get missed on a busy Friday are bids never submitted — invisible losses that never appear in any report.",
    userBenefit:
      "They send the email exactly as they do now. Nothing changes on their side, and nothing has to be explained to a customer.",
    demoNote:
      "Start here. Six lots, one email, and right now a person retypes all of it. Everything after this exists to serve that one shape.",
  },

  // ================================================= 1. inbox & dashboard
  {
    id: "app",
    // Also kept short: stages 1 and 2 are adjacent on the flow axis and, with
    // z left free, routinely foreshorten toward each other. The detail this
    // label drops is carried by the sub-line directly beneath it.
    label: "Dashboard",
    tier: "ui",
    parent: ROOT_ID,
    flowOrder: 1,
    sub: "Gmail label · Airtable views",
    logo: "airtable",
    icon: "browser",
    size: 9,
    what:
      "The two surfaces people actually touch: the Gmail inbox requests already arrive in, and the dashboard where the office sees where every job stands.",
    whyUsed:
      "Without a single board, 'where is that bid' is answered by searching a mailbox. The status lives in whoever's head last touched it, and that person is out on site.",
    clientBenefit:
      "The dashboard the brief asks for by name — one screen showing every bid and what has to happen next, instead of Gmail plus Joist plus a spreadsheet plus a phone call.",
    userBenefit:
      "Someone can answer 'what needs doing today' in a glance, rather than by reconstructing it from three systems.",
    demoNote:
      "Note what is not here: no new app for the project managers to learn. They keep emailing. The change is entirely on your side of the fence.",
  },
  {
    id: "monitored-inbox",
    label: "Monitored inbox",
    tier: "ui",
    parent: "app",
    sub: "a Gmail label, nothing more",
    logo: "gmail",
    icon: "browser",
    size: 5,
    what:
      "A designated Gmail label. Anything filed under it is picked up; anything else is ignored.",
    whyUsed:
      "Watching an entire mailbox means processing newsletters, invoices and reply-alls. A label makes the trigger explicit, and makes 'why didn't this get picked up' answerable in one look.",
    clientBenefit:
      "No mailbox migration, no forwarding rules, no new address to circulate to every builder. Setup is a Gmail filter, and it is reversible in a click.",
    userBenefit:
      "The office keeps working the way it already does, and can see at a glance which mail the system took.",
    demoNote:
      "This is deliberately the least clever part of the system. A label is something the client can change themselves without calling anyone.",
  },
  {
    id: "pipeline-board",
    label: "Pipeline board",
    tier: "ui",
    parent: "app",
    sub: "14 stages, as described",
    icon: "layers",
    size: 6,
    what:
      "Every bid on a board, in the fourteen stages the client described: Bid Request through PO Received, Deposit Paid, Crew Assigned, all the way to Closed.",
    whyUsed:
      "The stages come from the client's own brief rather than from a generic CRM template, so nobody has to translate their process into somebody else's vocabulary.",
    clientBenefit:
      "Jobs stuck between stages become visible. A deposit invoice that was never sent is currently only noticed when the crew shows up unpaid; here it is a count on a board.",
    userBenefit:
      "The pipeline reads the way the business actually runs, so nobody has to remember what a stage 'really' means.",
    demoNote:
      "These fourteen stages are lifted word for word from the brief. Look for a stage you don't recognise — there isn't one.",
  },
  {
    id: "review-ui",
    label: "Review queue",
    tier: "ui",
    parent: "app",
    sub: "extracted vs. original, side by side",
    icon: "compare",
    size: 6,
    what:
      "Anything the system was not confident about, shown next to the email it came from, with approve and reject.",
    whyUsed:
      "It is what makes conservative thresholds affordable. Being unsure costs one click here; being confidently wrong costs a duplicate job nobody finds for three weeks.",
    clientBenefit:
      "Uncertainty becomes a thirty-second decision instead of a silent error. The queue length is also the honest measure of how well extraction is doing — visible, not buried.",
    userBenefit:
      "You see what the system read and what it read it from, side by side. There is no black box to take on trust.",
    demoNote:
      "This screen is why the rest of the system can afford to be careful. Doubt has somewhere cheap to go.",
  },

  // ================================================= 2. ingestion gateway
  {
    id: "stage-gateway",
    // Short on purpose: this stage sits next to "Inbox & Dashboard" on the
    // flow axis and two wide labels there collide at narrower viewports.
    label: "Ingestion",
    tier: "gateway",
    parent: ROOT_ID,
    flowOrder: 2,
    sub: "Zapier · signed webhooks",
    logo: "zapier",
    icon: "gateway",
    size: 9,
    what:
      "Zapier watches the label and hands each message to the service over a signed webhook. It is the only way in.",
    whyUsed:
      "Zapier owns the orchestration because the client can maintain it. Triggers, notifications and routine field updates are all things they can change themselves, without a developer and without a deploy.",
    clientBenefit:
      "The parts most likely to need tweaking are the parts that need no engineer. Only the genuinely hard logic sits in code, which keeps the maintenance surface small.",
    userBenefit:
      "Requests appear in the system within a minute or two of landing in the inbox, with nobody pressing anything.",
    metric: {
      value: "1 Zap in",
      caption: "One trigger per document type — bids and POs — not a Zap per rule",
    },
    demoNote:
      "The split matters: Zapier does what Zapier is good at. What follows is the three things it genuinely cannot do.",
  },
  {
    id: "gmail-watch",
    label: "Gmail trigger",
    tier: "gateway",
    parent: "stage-gateway",
    sub: "new mail on a label",
    logo: "zapier",
    icon: "browser",
    size: 5,
    what: "Zapier's Gmail integration fires when a message lands on the watched label.",
    whyUsed:
      "Using Zapier's Gmail connection rather than the raw Gmail API avoids Google's OAuth app verification entirely — a process measured in weeks that produces no value for this client.",
    clientBenefit:
      "Removes a multi-week approval dependency from the critical path. Connecting the mailbox is a normal Google sign-in the office can do unaided.",
    userBenefit: "The office connects their own mailbox and nobody waits on anyone.",
    demoNote:
      "Worth saying out loud: this choice is about avoiding a Google review queue, not about capability.",
  },
  {
    id: "zap-webhook",
    label: "Signed webhook",
    tier: "gateway",
    parent: "stage-gateway",
    sub: "HMAC-SHA256 on the body",
    icon: "shield",
    size: 5,
    what:
      "Zapier signs each request body with a shared secret; the service verifies it before reading a single field.",
    whyUsed:
      "A webhook URL is a URL. Without a signature, anyone who ever sees it in a log, a screenshot or a support ticket can write into the client's live job data.",
    clientBenefit:
      "A leaked URL is not enough to create fake jobs or alter approved amounts. The comparison is constant-time, so the secret cannot be recovered by timing the endpoint.",
    userBenefit: "Nothing to notice — which is the entire objective.",
    demoNote:
      "Cheap to add on day one, awkward to retrofit once a client's real POs are flowing through it.",
  },
  {
    id: "idempotency",
    label: "Idempotency gate",
    tier: "gateway",
    parent: "stage-gateway",
    sub: "keyed on the Gmail message id",
    icon: "compare",
    size: 7,
    what:
      "Each extracted record gets a key derived from the message id and its position in the email. A replay re-derives exactly the same keys and creates nothing.",
    whyUsed:
      "Zapier retries any step that fails, and Gmail can redeliver. Without this, one flaky minute turns six bids into twelve — and duplicates in a bid pipeline are the failure the brief calls out by name.",
    clientBenefit:
      "The check runs before the model is called, not after, so a retry storm is free as well as harmless. Re-processing costs nothing at all.",
    userBenefit:
      "Nobody ever opens the board and finds the same lot listed twice with no way to tell which one is real.",
    metric: {
      value: "$0.00",
      caption: "Cost of a replayed email — the gate sits ahead of the model call",
    },
    demoNote:
      "Watch this: I'll post the same email twice. The second time creates nothing and costs nothing.",
  },

  // ================================================= 3. document assembly
  {
    id: "stage-context",
    label: "Document Assembly",
    tier: "context",
    parent: ROOT_ID,
    flowOrder: 3,
    sub: "what the model is shown",
    icon: "brain",
    size: 9,
    what:
      "Turns a raw email or PDF into the exact document the model reads: headers separated from body, attachments attached, and the currently open bids available for comparison.",
    whyUsed:
      "Extraction quality is set here more than in the prompt. A model shown a subject line mashed into a quoted reply chain will confidently attribute the wrong property to the wrong lot.",
    clientBenefit:
      "Fewer wrong extractions for no extra inference cost — this stage is ordinary code. It is the cheapest accuracy available.",
    userBenefit: "Forwarded threads and reply chains are read correctly rather than doubling up work already captured.",
    demoNote:
      "Unglamorous and load-bearing. Most extraction failures I have seen are assembly failures wearing a prompt's clothes.",
  },
  {
    id: "email-normalize",
    label: "Email structuring",
    tier: "context",
    parent: "stage-context",
    sub: "subject, body and quoted chain tagged",
    icon: "layers",
    size: 5,
    what:
      "Sender, subject, timestamp and body are tagged separately rather than concatenated into one blob.",
    whyUsed:
      "Headers and quoted history routinely name a different property than the live request. Tagging lets the model tell 'what is being asked now' from 'what was asked last Tuesday'.",
    clientBenefit:
      "Reply-all threads stop re-creating bids that already exist — the most common source of duplicates after outright retries.",
    userBenefit:
      "A PM can reply in-thread, the way they already do, without it being read as six new requests.",
    demoNote:
      "The fixture email here has a quoted chain underneath. Only the top half is treated as a request.",
  },
  {
    id: "pdf-document",
    label: "PDF handling",
    tier: "context",
    parent: "stage-context",
    sub: "native document block",
    logo: "claude",
    icon: "archive",
    size: 6,
    what:
      "PO PDFs are passed to the model as a document, not converted to text first.",
    whyUsed:
      "Text extraction libraries lose table layout, and fail outright on the scanned and photographed POs that arrive constantly in this trade. Passing the document keeps the layout the amount depends on.",
    clientBenefit:
      "No OCR service to license, run or debug, and scanned POs work on day one rather than being the exception that quietly stays manual.",
    userBenefit:
      "A phone photo of a PO taped to a job trailer wall reads as well as a clean export.",
    demoNote:
      "The sample PO puts a materials subtotal above the approved total on purpose. Layout is what tells them apart.",
  },
  {
    id: "candidate-lookup",
    label: "Candidate lookup",
    tier: "context",
    parent: "stage-context",
    sub: "open bids, fetched before matching",
    icon: "database",
    size: 5,
    what:
      "Pulls the currently open bids so an incoming PO or revision can be compared against live state rather than against the sender's description of it.",
    whyUsed:
      "A PM writing 'revised scope below' for a bid that was never entered is describing new work, whatever they called it. Only the database can settle that.",
    clientBenefit:
      "Cancellations and revisions are resolved against what is actually on file, which is what stops a mislabelled email from editing the wrong job.",
    userBenefit: "The system's answer matches what is on the board, not what an email claimed.",
    demoNote:
      "The sender's framing is treated as a hint. The database is treated as the fact.",
  },

  // ================================================= 4. THE ENGINE
  {
    id: "stage-engine",
    label: "Extraction & Matching",
    tier: "engine",
    parent: ROOT_ID,
    flowOrder: 4,
    sub: "Claude Opus 5 · three-tier matcher",
    logo: "claude",
    icon: "chip",
    size: 12,
    what:
      "The three things Zapier genuinely cannot do: split one email into many records, match a PO to the bid it belongs to, and tell a revision apart from a duplicate.",
    whyUsed:
      "Everything else here is plumbing that a competent Zapier consultant could assemble. This stage is the reason the system is worth building rather than configuring.",
    clientBenefit:
      "At roughly four cents an email, the model costs less than a minute of anyone's time. The comparison is not against a cheaper model — it is against the twenty minutes of retyping this replaces.",
    userBenefit:
      "The board is populated before anyone has opened the email, so the first human action is estimating rather than transcribing.",
    metric: {
      value: "≈ $0.04",
      caption:
        "Per bid-request email. 2.4K in × $5/MTok + 0.9K out × $25/MTok, at Claude Opus 5 list rates",
    },
    demoNote:
      "This is the stage the money argument rests on. Open it — every part in here earns its place, including the one that is switched off.",
  },
  {
    id: "bid-splitter",
    label: "Multi-lot splitter",
    tier: "engine",
    parent: "stage-engine",
    sub: "one email → N records",
    icon: "scissors",
    size: 8,
    what:
      "Reads one email and returns one entry per property and lot. Six lots produce six records, each with its own address, scope and due date.",
    whyUsed:
      "It is the single most valuable operation in the system, and the one no rule-based tool does reliably. Lots are listed in prose, in tables, in bullet lists, and with scopes that apply to some lots but not others.",
    clientBenefit:
      "Turns the most expensive manual step — reading and retyping a multi-lot request — into something that has already happened by the time anyone opens the mail.",
    userBenefit:
      "The lots that used to get missed at the bottom of a long email are simply there.",
    metric: {
      value: "6 → 6",
      caption:
        "Fixture: a six-lot email produces six records, verified in the offline test suite",
    },
    demoNote:
      "The instruction that matters most is the negative one: never merge two lots, and never split one lot because its scope ran to two sentences.",
  },
  {
    id: "field-extractor",
    label: "Field extraction",
    tier: "engine",
    parent: "stage-engine",
    sub: "schema-enforced, not parsed",
    logo: "claude",
    icon: "brain",
    size: 6,
    what:
      "Pulls property, lot, address, city, state, scope and due date into a schema the API enforces on the model.",
    whyUsed:
      "The schema is validated at the tool-call layer, so a malformed response is retried by the API rather than reaching our code. There is no JSON parsing and no regex anywhere in this path.",
    clientBenefit:
      "Removes the whole class of failure where a model returns something almost-valid and a parser silently drops a field. Structural correctness stops being something we have to defend.",
    userBenefit: "Fields land where they belong, or the record goes to review. There is no third outcome.",
    demoNote:
      "A field that isn't stated stays empty. It never infers a city from a subdivision name — a guess in this column becomes a truck at the wrong address.",
  },
  {
    id: "po-extractor",
    label: "PO reading",
    tier: "engine",
    parent: "stage-engine",
    sub: "number, property, lot, amount",
    icon: "ledger",
    size: 6,
    what:
      "Reads the PO number, the property and lot it refers to, and the approved amount — from an email body, a PDF, or both together.",
    whyUsed:
      "The approved amount drives the 50% deposit invoice, so a misread here bills the customer the wrong number. POs commonly show several figures: a materials subtotal, a labour subtotal, tax, and the approved total.",
    clientBenefit:
      "The deposit is computed from the approved contract value rather than whichever number sat nearest the bottom of the page.",
    userBenefit: "The deposit figure on the alert is the one that belongs on the invoice.",
    demoNote:
      "If it cannot tell which figure is the approved total, it returns nothing and says so. A null goes to review; a wrong number goes to a customer.",
  },
  {
    id: "bid-matcher",
    label: "Three-tier matcher",
    tier: "engine",
    parent: "stage-engine",
    sub: "exact → fuzzy → adjudicated",
    icon: "compare",
    size: 9,
    what:
      "Attaches an incoming PO to the bid it belongs to. Exact property-and-lot key first; fuzzy string matching second; the model only for what is genuinely ambiguous.",
    whyUsed:
      "Answers the brief's requirement to match POs to existing bids and prevent duplicate jobs. The tiering is the design: the model is the last resort, not the first, so most POs resolve at zero marginal cost and zero latency.",
    clientBenefit:
      "The expensive tier runs only on the small ambiguous remainder — the only place its judgement is worth paying for. The cheap tiers carry the volume.",
    userBenefit:
      "'Willow Crk' still finds Willow Creek. A typo in an AP department's template does not create a second job.",
    metric: {
      value: "2 free tiers",
      caption:
        "Exact and fuzzy cost nothing per PO; only genuine ambiguity reaches the model",
      estimated: true,
    },
    demoNote:
      "The rule that does the work is the margin, not the score. Two lots in one subdivision both scoring 93% is exactly the case that must not auto-apply.",
  },
  {
    id: "revision-classifier",
    label: "Revision vs duplicate",
    tier: "engine",
    parent: "stage-engine",
    sub: "new · revision · addition · cancellation",
    icon: "loop",
    size: 9,
    what:
      "Decides whether an inbound bid is new work, an edit to an existing job, an extra lot, or a cancellation — by comparing it to live state, not to the email's wording.",
    whyUsed:
      "This is the brief's hardest sentence: handle changes 'without creating duplicates or accidentally deleting valid bids'. A stable fingerprint of property plus lot survives a scope change, so a revision resolves to the same job instead of a second record.",
    clientBenefit:
      "Revisions update in place with the previous values kept, so 'what did this bid say last Tuesday' is always answerable. Nothing is overwritten and nothing is lost.",
    userBenefit:
      "A PM can revise the same lot four times and the board still shows one job with a history, not four competing rows.",
    metric: {
      value: "0 deletes",
      caption: "No code path in the system deletes a bid record — by design, not by omission",
    },
    demoNote:
      "'42', 'Lot 42' and 'L-42' are one lot. Getting that wrong is precisely how duplicates are born.",
  },
  {
    id: "confidence-gate",
    label: "Confidence gate",
    tier: "engine",
    parent: "stage-engine",
    sub: "under 80% → a human",
    icon: "shield",
    size: 7,
    what:
      "Every extraction reports how sure it is and which fields it was unsure about. Below the threshold, nothing is applied automatically.",
    whyUsed:
      "It converts the model's uncertainty into an action instead of leaving it as a number in a log. Without a gate, the only options are trusting everything or checking everything.",
    clientBenefit:
      "The threshold is a dial the client owns. Set it high while trust is being earned and lower it once the queue proves boring — no code change either way.",
    userBenefit:
      "Uncertain records arrive with the doubtful field already named, so review is a glance rather than a re-read.",
    demoNote:
      "The prompt tells the model that a low score is cheap and a confidently wrong answer is not. That framing is doing real work.",
  },
  {
    id: "auto-cancel",
    label: "Automatic cancellation",
    tier: "engine",
    parent: "stage-engine",
    sub: "built, and switched off",
    icon: "thumb",
    size: 7,
    what:
      "Detects that an email cancels a previously requested bid, and could set the status without asking.",
    whyUsed:
      "Detection is genuinely reliable — cancellations are stated plainly and rarely ambiguous. The capability works.",
    clientBenefit:
      "**Not enabled by default, and this is deliberate.** A misread cancellation stands a crew down on a live job, and it is not recoverable from the email thread alone: nobody notices an absence. The saving would be a few seconds a week; the failure costs a scheduled crew. Cancellations are detected, queued, and applied on one click.",
    userBenefit:
      "A cancellation appears in the queue in seconds with the sentence that triggered it quoted. Someone confirms, rather than discovering later that a job vanished.",
    metric: {
      value: "Off",
      caption:
        "Config flag exists and is documented; disabled by default. Never auto-applies to a job with a PO attached, whatever the flag says",
    },
    demoNote:
      "This is the honest one. Everything else here is automated because automating it is safe. This one isn't, and the reason is asymmetry, not capability.",
  },

  // ================================================= 5. airtable
  {
    id: "stage-data",
    label: "Airtable Base",
    tier: "data",
    parent: ROOT_ID,
    flowOrder: 5,
    sub: "9 tables, defined as code",
    logo: "airtable",
    icon: "database",
    size: 9,
    what:
      "Nine linked tables — bids, POs, invoices, payments, properties, clients, crews, materials, and the run log — created from a schema checked into version control.",
    whyUsed:
      "Airtable because the client's team can work in it unaided. Schema as code because a base built by clicking is a base nobody can review, reproduce, or rebuild.",
    clientBenefit:
      "The base can be rebuilt in a fresh workspace from one command, and a schema change arrives as a reviewable diff rather than as somebody's afternoon.",
    userBenefit: "It looks and behaves like the Airtable the team already knows.",
    metric: {
      value: "9 tables",
      caption: "Provisioned by script; re-running only adds what is missing",
    },
    demoNote:
      "Worth showing the file. The schema is the source of truth, and the documentation is generated from it — so they cannot drift.",
  },
  {
    id: "bids-table",
    label: "Bids",
    tier: "data",
    parent: "stage-data",
    sub: "one row per lot",
    icon: "layers",
    size: 7,
    what:
      "The spine: one record per property and lot, carrying scope, due date, estimator, status and the fingerprint that identifies the job.",
    whyUsed:
      "Everything else links to a bid. Getting the grain right — one row per lot, not per email — is what makes the fourteen-stage pipeline mean anything.",
    clientBenefit:
      "Each lot moves through the pipeline independently, so a stalled lot is visible instead of being hidden inside a batch marked 'in progress'.",
    userBenefit: "The board shows jobs, at the granularity people actually talk about them.",
    demoNote:
      "The fingerprint column is the quiet hero. It is how a revision three weeks later finds this exact row.",
  },
  {
    id: "linked-records",
    label: "Linked records",
    tier: "data",
    parent: "stage-data",
    sub: "PO → bid → invoice → payment",
    icon: "cluster",
    size: 6,
    what:
      "POs link to bids, invoices to bids, payments to invoices, materials and crews to the job.",
    whyUsed:
      "It makes 'has this been paid' a link to follow rather than a search. It is also what lets a cancelled job keep its financial history intact instead of orphaning it.",
    clientBenefit:
      "Deposit-paid-but-not-scheduled, and completed-but-never-invoiced, become filters instead of the kind of thing found during a bad month.",
    userBenefit: "One click from a job to the money attached to it.",
    demoNote:
      "The links are also why nothing is ever hard-deleted — a delete here would orphan real financial records.",
  },
  {
    id: "version-history",
    label: "Change history",
    tier: "data",
    parent: "stage-data",
    sub: "old values, written before the update",
    icon: "archive",
    size: 7,
    what:
      "Before a revision is applied, the previous field values are written to the run log with the reason and the source email.",
    whyUsed:
      "Update-in-place is what prevents duplicates, but on its own it destroys the prior state. The history is what makes the trade safe.",
    clientBenefit:
      "Every revision is reversible and attributable. 'They never told us to change that' is settled by looking, not by arguing.",
    userBenefit:
      "The change is on the record with the email that caused it, so a disputed scope is a lookup rather than a memory test.",
    metric: {
      value: "Write-before-update",
      caption:
        "History is committed before the change lands, so an interrupted update still leaves the old state recoverable",
    },
    demoNote:
      "Order matters here. The old value is written first — if the update fails halfway, you can still see what it was.",
  },

  // ================================================= 6. audit & review
  {
    id: "stage-ops",
    label: "Audit & Review",
    tier: "ops",
    parent: ROOT_ID,
    flowOrder: 6,
    sub: "every decision, with its cost",
    icon: "chart",
    size: 9,
    what:
      "An append-only log of every extraction, match and decision — with the model used, the tokens spent, and what it cost.",
    whyUsed:
      "Because 'the AI did something odd' has to be answerable. Without a trail, the only debugging tool is re-running the email and hoping it misbehaves again.",
    clientBenefit:
      "The system's accuracy and its running cost are both checkable by the client, from their own base, without asking us. Trust stops being something they have to extend on faith.",
    userBenefit: "Anything surprising can be traced back to the email that caused it, in seconds.",
    demoNote:
      "This is what makes the cost figures on this page verifiable rather than promotional. They come out of here.",
  },
  {
    id: "run-log",
    label: "Run log",
    tier: "ops",
    parent: "stage-ops",
    sub: "append-only, with token counts",
    icon: "ledger",
    size: 7,
    what:
      "One row per event: what came in, what was decided, why, which model, how many tokens, and the cost.",
    whyUsed:
      "It doubles as the debugging trail and the invoice. A cost surprise is diagnosable down to the individual email that caused it.",
    clientBenefit:
      "Spend is attributable per email rather than arriving as one opaque monthly figure, so an unusual bill has a cause you can point at.",
    userBenefit: "Nothing to look at until something looks wrong — and then everything is there.",
    metric: {
      value: "Per-email cost",
      caption: "Derived from published list pricing and the actual token counts returned",
    },
    demoNote:
      "Logging never blocks ingest. If the audit write fails, the work still lands — the log is evidence, not a gate.",
  },
  {
    id: "review-queue",
    label: "Human review",
    tier: "ops",
    parent: "stage-ops",
    sub: "the only place uncertainty goes",
    icon: "thumb",
    size: 8,
    what:
      "Everything the system declined to do on its own: low-confidence extractions, ambiguous PO matches, all cancellations, and revisions to jobs that already have money attached.",
    whyUsed:
      "It is the counterweight that makes conservative thresholds affordable. Every safety rule in the system routes here rather than to a silent failure or a dropped record.",
    clientBenefit:
      "The queue is the system's own honesty check: a short queue means extraction is working, a long one is a measurable signal rather than a vague feeling.",
    userBenefit:
      "Nothing is ever silently dropped. If the system was unsure, it says so, in a place someone is already looking.",
    demoNote:
      "Notice what lands here: flagged items are still written to the base. Parked, not discarded — an unwritten item is one nobody can find.",
  },
  {
    id: "cost-telemetry",
    label: "Cost telemetry",
    tier: "ops",
    parent: "stage-ops",
    sub: "list pricing × actual tokens",
    icon: "chart",
    size: 6,
    what:
      "Every call's token usage is priced at published rates and stored alongside the decision it paid for.",
    whyUsed:
      "So the running cost is a measured number rather than an estimate that ages badly. Prompt caching means the same email costs less the second time, and that shows up here rather than being assumed.",
    clientBenefit:
      "Volume changes translate into a cost projection from real data, so scaling up is a calculation rather than a gamble.",
    userBenefit: "No bill shock, and no need to take anyone's word for the unit economics.",
    demoNote:
      "The four-cent figure on the engine card comes from this, not from a slide. You can re-derive it from the log.",
  },

  // ================================================= 7. platform & joist
  {
    id: "stage-platform",
    label: "Platform & Joist",
    tier: "platform",
    parent: ROOT_ID,
    flowOrder: 7,
    sub: "how it runs, and what it won't touch",
    icon: "cluster",
    size: 9,
    what:
      "Where the pieces are deployed, who maintains which part, and — the question the brief asks directly — exactly what can and cannot be automated with Joist.",
    whyUsed:
      "The brief asks for an honest assessment rather than a promise. This stage is that assessment, including the part that is a straight no.",
    clientBenefit:
      "The boundary is drawn before work starts rather than discovered in week three, when it becomes a change order and an awkward conversation.",
    userBenefit: "Nobody is told a step is automated and then finds themselves still doing it by hand.",
    demoNote:
      "This stage is where I would be sceptical of any proposal, including this one. Open the Joist card.",
  },
  {
    id: "zapier-orchestration",
    label: "Zapier orchestration",
    tier: "platform",
    parent: "stage-platform",
    sub: "the client-maintainable half",
    logo: "zapier",
    icon: "loop",
    size: 7,
    what:
      "Four Zaps: bid intake, PO intake, the deposit-needed alert, and payment status coming back from QuickBooks.",
    whyUsed:
      "Everything a non-developer might reasonably want to change — who gets notified, which label is watched, what the alert says — lives where they can change it.",
    clientBenefit:
      "Reduces the standing dependency on us. Routine changes do not become billable tickets, which is also what makes a contract-to-hire arrangement honest.",
    userBenefit: "The office can adjust their own notifications without booking anyone's time.",
    demoNote:
      "Deliberate division of labour: Zapier holds what should be editable, code holds what must be correct.",
  },
  {
    id: "fastapi-service",
    label: "Extraction service",
    tier: "platform",
    parent: "stage-platform",
    sub: "FastAPI · stateless",
    logo: "fastapi",
    icon: "chip",
    size: 7,
    what:
      "A small stateless Python service holding the extraction, matching and revision logic. Airtable is the only state.",
    whyUsed:
      "Stateless means it can be redeployed, restarted or scaled without a migration, and a failed request is always safe to retry.",
    clientBenefit:
      "No database to run, back up or pay for beyond Airtable itself. The operational surface is one process and one hosted base.",
    userBenefit: "Deploys are invisible; a restart mid-email costs a retry, not a record.",
    metric: {
      value: "76 tests",
      caption:
        "The suite runs with no API key and no network — the safety rules are verifiable by anyone who clones the repo",
    },
    demoNote:
      "The whole suite runs offline. That is not a nicety: it means these guarantees are checkable rather than asserted.",
  },
  {
    id: "joist-bridge",
    label: "Joist boundary",
    tier: "platform",
    parent: "stage-platform",
    sub: "no API — and no workaround",
    logo: "joist",
    icon: "shield",
    size: 9,
    what:
      "Joist publishes no REST API and has no Zapier app. Converting an estimate into an invoice and sending it stays a manual step in Joist.",
    whyUsed:
      "Because it is true, and it is the question the brief actually asked. An unofficial reverse-engineered layer for Joist does exist. **We are deliberately not using it**: it drives an authenticated session Joist never published, it breaks whenever they ship a UI change, and it sits outside their terms — which is a poor foundation for the system that issues your invoices.",
    clientBenefit:
      "What is automated is everything either side of the click: the alert that a deposit invoice is due with the amount already calculated, and the payment status read back afterwards. The estimated saving is the searching and the arithmetic, not the invoicing itself — but that is where the time actually goes.",
    userBenefit:
      "The office is told exactly which job needs an invoice and for how much, instead of noticing it three days later. They still press the button in Joist.",
    metric: {
      value: "1 manual step",
      caption:
        "Estimate → invoice in Joist. Verified Aug 2026: no public API, no Zapier app",
    },
    demoNote:
      "I would rather lose the job than promise a Joist integration that does not exist. Everything either side of this click is automated; this click is not.",
  },
  {
    id: "quickbooks-readback",
    label: "QuickBooks read-back",
    tier: "platform",
    parent: "stage-platform",
    sub: "the seam that does exist",
    logo: "quickbooks",
    icon: "loop",
    size: 8,
    what:
      "Joist syncs natively to QuickBooks Online. QuickBooks has a real API and a Zapier app, so payment status flows back into Airtable from there.",
    whyUsed:
      "It is the one genuine integration seam Joist offers. Reading payment state through the accounting system the client already reconciles against is both possible and more trustworthy than scraping.",
    clientBenefit:
      "Closes the loop from deposit invoice to deposit paid without anyone retyping it, using a supported API — so it keeps working after Joist's next release.",
    userBenefit:
      "'Deposit Paid' appears on the board on its own, and the crew scheduling that waits on it stops waiting.",
    metric: {
      value: "Supported API",
      caption:
        "QuickBooks Online, via its published API and Zapier app — unlike the Joist path",
      estimated: true,
    },
    demoNote:
      "This is the answer to the Joist question. Not 'we'll integrate Joist' — go around it, through the system Joist itself syncs to.",
  },
];

// ---------------------------------------------------------------------------
// Links
// ---------------------------------------------------------------------------

export interface ArchLink {
  source: string;
  target: string;
  /**
   * `tree` is containment. `request` is the live path a document takes.
   * `context` is data pulled *into* the engine. `improve` is the two edges
   * that flow back upstream -- a human correction landing, and payment status
   * returning -- and they get the strongest colour because being able to see
   * that the loop closes is most of what distinguishes this from a one-way
   * import script.
   */
  kind:
    | "tree"
    | "request"
    | "context"
    | "data"
    | "observe"
    | "improve"
    | "platform";
  label?: string;
}

export const LINKS: ArchLink[] = [
  // --- the request path -------------------------------------------------
  { source: "pm", target: "monitored-inbox", kind: "request", label: "bid request email" },
  { source: "monitored-inbox", target: "gmail-watch", kind: "request", label: "label fires" },
  { source: "gmail-watch", target: "zap-webhook", kind: "request" },
  { source: "zap-webhook", target: "idempotency", kind: "request" },
  { source: "idempotency", target: "email-normalize", kind: "request", label: "first time only" },
  { source: "email-normalize", target: "bid-splitter", kind: "request" },
  { source: "pdf-document", target: "po-extractor", kind: "request", label: "PO PDFs" },

  // --- context pulled into the engine -----------------------------------
  { source: "candidate-lookup", target: "bid-matcher", kind: "context", label: "open bids" },
  { source: "candidate-lookup", target: "revision-classifier", kind: "context" },
  { source: "bid-splitter", target: "field-extractor", kind: "request" },
  { source: "field-extractor", target: "revision-classifier", kind: "request" },
  { source: "po-extractor", target: "bid-matcher", kind: "request" },
  { source: "revision-classifier", target: "confidence-gate", kind: "request" },
  { source: "bid-matcher", target: "confidence-gate", kind: "request" },
  { source: "auto-cancel", target: "confidence-gate", kind: "request", label: "queued, not applied" },

  // --- persistence -------------------------------------------------------
  { source: "confidence-gate", target: "bids-table", kind: "data", label: "confident only" },
  { source: "bids-table", target: "linked-records", kind: "data" },
  { source: "bids-table", target: "version-history", kind: "data", label: "before update" },

  // --- observation -------------------------------------------------------
  { source: "bids-table", target: "run-log", kind: "observe" },
  { source: "version-history", target: "run-log", kind: "observe" },
  { source: "confidence-gate", target: "review-queue", kind: "observe", label: "uncertain" },
  { source: "run-log", target: "cost-telemetry", kind: "observe" },

  // --- back upstream: the loops that close --------------------------------
  { source: "review-queue", target: "bids-table", kind: "improve", label: "human approves" },
  { source: "bids-table", target: "pipeline-board", kind: "data", label: "the board reads here" },
  { source: "review-queue", target: "review-ui", kind: "data" },

  // --- platform ----------------------------------------------------------
  { source: "run-log", target: "fastapi-service", kind: "platform" },
  { source: "cost-telemetry", target: "fastapi-service", kind: "platform" },
  { source: "fastapi-service", target: "zapier-orchestration", kind: "platform" },
  { source: "bids-table", target: "joist-bridge", kind: "platform", label: "deposit needed" },
  { source: "joist-bridge", target: "quickbooks-readback", kind: "platform", label: "native sync" },
  { source: "quickbooks-readback", target: "bids-table", kind: "improve", label: "deposit paid" },
];

// ---------------------------------------------------------------------------
// Derived -- no need to edit below this line
// ---------------------------------------------------------------------------

export const NODE_BY_ID = new Map(NODES.map((n) => [n.id, n]));
export const TIER_BY_ID = new Map(TIERS.map((t) => [t.id, t]));

export const CHILDREN_BY_PARENT = NODES.reduce((map, node) => {
  if (!node.parent) return map;
  const siblings = map.get(node.parent) ?? [];
  siblings.push(node);
  map.set(node.parent, siblings);
  return map;
}, new Map<string, ArchNode[]>());

export function hasChildren(id: string): boolean {
  return (CHILDREN_BY_PARENT.get(id)?.length ?? 0) > 0;
}

export function ancestorsOf(id: string): string[] {
  const chain: string[] = [];
  let current = NODE_BY_ID.get(id)?.parent;
  while (current) {
    chain.push(current);
    if (current === ROOT_ID) break;
    current = NODE_BY_ID.get(current)?.parent;
  }
  return chain;
}

/** Containment edges, derived from `parent` so the two can never disagree. */
export const TREE_LINKS: ArchLink[] = NODES.filter((n) => n.parent).map((n) => ({
  source: n.parent!,
  target: n.id,
  kind: "tree" as const,
}));

/** Top-level stages, in pipeline order. */
export const STAGES = NODES.filter((n) => n.flowOrder !== undefined).sort(
  (a, b) => a.flowOrder! - b.flowOrder!,
);

// ---------------------------------------------------------------------------
// Guided tour -- the thing that gets recorded
// ---------------------------------------------------------------------------

export interface TourStop {
  nodeId: string;
  chapter: string;
  say: string;
}

export const TOUR: TourStop[] = [
  {
    nodeId: "pm",
    chapter: "1 · The problem",
    say: "This is where it starts: a project manager emails a bid request, and one email covers six lots. Right now somebody reads that and retypes all six by hand — and the ones that get missed on a busy Friday are bids you never submitted.",
  },
  {
    nodeId: "monitored-inbox",
    chapter: "2 · Nothing changes for them",
    say: "The first design decision is what we don't do. No portal, no new address, no asking your builders to change anything. A Gmail label, which your office controls and can turn off in one click.",
  },
  {
    nodeId: "pipeline-board",
    chapter: "3 · The one screen",
    say: "This is the dashboard the brief asks for — every bid, in the fourteen stages you described. Those stages are lifted word for word from your own process; look for one you don't recognise.",
  },
  {
    nodeId: "review-ui",
    chapter: "4 · Where doubt goes",
    say: "And this is the screen that makes the rest of it safe. Anything the system wasn't sure about lands here next to the original email. Doubt costs thirty seconds instead of becoming a silent mistake.",
  },
  {
    nodeId: "stage-gateway",
    chapter: "5 · The division of labour",
    say: "Zapier does the orchestration, because you can maintain Zapier without calling me. What follows is the three things Zapier genuinely cannot do — and that's the part worth paying for.",
  },
  {
    nodeId: "zap-webhook",
    chapter: "6 · The boring safety",
    say: "Every request is signed. A webhook URL is just a URL — anyone who sees it in a screenshot could otherwise write into your live job data. Cheap now, awkward once real POs are flowing.",
  },
  {
    nodeId: "idempotency",
    chapter: "7 · Retries are free",
    say: "Zapier retries whatever fails, and Gmail redelivers. This gate sits ahead of the model, so a replay creates nothing and costs nothing. I'll post the same email twice later and you'll see zero happen.",
  },
  {
    nodeId: "stage-context",
    chapter: "8 · Feeding it properly",
    say: "Most extraction failures are actually assembly failures. Tagging the subject separately from the quoted reply chain is ordinary code — it's the cheapest accuracy in the system.",
  },
  {
    nodeId: "pdf-document",
    chapter: "9 · Scanned POs",
    say: "POs go to the model as documents, not converted to text first. That matters because half of them are photos taken in a job trailer, and a text library gives you nothing from those.",
  },
  {
    nodeId: "stage-engine",
    chapter: "10 · The engine",
    say: "Here's the stage the whole cost argument rests on. About four cents per email, at published rates — you can check that arithmetic. Compare it not to a cheaper model but to the twenty minutes of retyping it replaces.",
  },
  {
    nodeId: "bid-splitter",
    chapter: "11 · Six from one",
    say: "This is the single most valuable operation in the system. One email, six lots, six separate jobs — each with its own address, scope and due date. No rule-based tool does this reliably; they're listed in prose one week and a table the next.",
  },
  {
    nodeId: "field-extractor",
    chapter: "12 · No parsing",
    say: "The schema is enforced by the API on the model, so there's no JSON parsing anywhere. And a field that isn't stated stays empty — it never infers a city from a subdivision name, because a guess in that column is a truck at the wrong address.",
  },
  {
    nodeId: "po-extractor",
    chapter: "13 · The right number",
    say: "The approved amount drives your 50% deposit, so a misread bills your customer wrong. POs show four or five figures. If it can't tell which is the approved total, it returns nothing — a null goes to review, a wrong number goes to a customer.",
  },
  {
    nodeId: "bid-matcher",
    chapter: "14 · Matching, cheaply",
    say: "Three tiers: exact key, then fuzzy, and the model only for what's genuinely ambiguous. The cheap tiers carry the volume. The rule that does the real work isn't the score, it's the margin — two lots in one subdivision both scoring 93% is exactly what must not auto-apply.",
  },
  {
    nodeId: "revision-classifier",
    chapter: "15 · The hard requirement",
    say: "Your brief asks for revisions and cancellations without duplicates and without losing valid bids. A fingerprint of property and lot survives a scope change, so a revision finds the same job. '42', 'Lot 42' and 'L-42' are one lot — getting that wrong is how duplicates are born.",
  },
  {
    nodeId: "confidence-gate",
    chapter: "16 · A dial you own",
    say: "Every extraction says how sure it is and which field it doubted. Below the threshold nothing auto-applies. Set it high while we're earning trust, lower it once the queue gets boring — that's a config change, not a rebuild.",
  },
  {
    nodeId: "auto-cancel",
    chapter: "17 · What I turned off",
    say: "Cancellation detection works reliably, and I've left it switched off. A misread cancellation stands your crew down on a live job and nobody notices an absence. It saves seconds a week and risks a scheduled crew — so it queues for one click instead.",
  },
  {
    nodeId: "bids-table",
    chapter: "18 · One row per lot",
    say: "The grain matters: one record per lot, not per email. That's what makes the fourteen stages mean anything — a stalled lot is visible instead of hidden inside a batch marked 'in progress'.",
  },
  {
    nodeId: "version-history",
    chapter: "19 · Nothing is lost",
    say: "Updating in place is what prevents duplicates, but on its own it destroys what was there before. So the old values are written first, with the email that caused the change. 'They never told us to change that' becomes a lookup instead of an argument.",
  },
  {
    nodeId: "review-queue",
    chapter: "20 · Never silently dropped",
    say: "Everything the system declined to do lands here — and note flagged items are still written to the base. Parked, not discarded. An unwritten record is one nobody can find.",
  },
  {
    nodeId: "run-log",
    chapter: "21 · Check my numbers",
    say: "Every decision logged with its token count and its cost. This is what makes the four cents on that engine card verifiable rather than promotional — you can re-derive it from your own base, without asking me.",
  },
  {
    nodeId: "joist-bridge",
    chapter: "22 · The honest answer",
    say: "You asked what's realistic with Joist. Joist publishes no API and has no Zapier app. There's an unofficial reverse-engineered layer and I'm not using it — it breaks on any Joist UI change and sits outside their terms. Converting the estimate stays a manual click.",
  },
  {
    nodeId: "quickbooks-readback",
    chapter: "23 · Going around it",
    say: "But Joist syncs natively to QuickBooks, and QuickBooks has a real API. So we automate everything either side of that click: the alert with the deposit already calculated, and the payment status read back afterwards. That's the difference between a promise and a plan.",
  },
  {
    nodeId: "zapier-orchestration",
    chapter: "24 · Who owns what",
    say: "Which leaves the question of running it. Zapier holds what should be editable — notifications, labels, alert wording — so routine changes never become billable tickets. Code holds only what must be correct. That's what makes this maintainable after I'm gone.",
  },
];

export { TIERS as ARCH_TIERS };
