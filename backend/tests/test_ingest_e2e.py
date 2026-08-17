"""End-to-end ingest, with the model stubbed and Airtable in memory.

This is the demo, as a test. The extraction call is replaced with a canned
BidRequestBatch so the assertions are about orchestration -- the split, the
idempotency, the safety rules, the audit trail -- rather than about model
behaviour, which is not deterministic and is not what these tests are for.
"""

from __future__ import annotations

from datetime import date

import pytest

from app import ingest
from app.airtable import client as at
from app.extraction.client import ExtractionResult, Usage
from app.extraction.schemas import (
    BidRequestBatch,
    EmailIntent,
    ExtractedBid,
    ExtractedPurchaseOrder,
)
from app.pipeline import Stage
from app.demo import InMemoryRepository

USAGE = Usage(
    input_tokens=2_400,
    output_tokens=900,
    cache_read_tokens=0,
    cache_write_tokens=0,
    model="claude-opus-5",
)


def _six_lot_batch() -> BidRequestBatch:
    """One email, six lots -- the case the client called out by name."""
    return BidRequestBatch(
        project_manager="Dana Reyes",
        client_company="Copperline Homes",
        intent=EmailIntent.NEW_REQUEST,
        summary="Six lots at Willow Creek Phase 2, flooring, due 12 Sep.",
        bids=[
            ExtractedBid(
                property_name="Willow Creek Phase 2",
                lot_number=f"Lot {lot}",
                city="Boise",
                state="ID",
                scope_of_work="R&R carpet and pad throughout",
                bid_due_date=date(2026, 9, 12),
                confidence=0.95,
            )
            for lot in (41, 42, 43, 44, 45, 46)
        ],
    )


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def stub_extraction(monkeypatch: pytest.MonkeyPatch):
    def _install(batch: BidRequestBatch):
        calls = {"count": 0}

        def _fake(**_kwargs):
            calls["count"] += 1
            return ExtractionResult(parsed=batch, usage=USAGE)

        monkeypatch.setattr(ingest, "extract_bids", _fake)
        return calls

    return _install


# --- the headline behaviour --------------------------------------------


def test_one_email_becomes_six_records(repo, stub_extraction):
    stub_extraction(_six_lot_batch())

    result = ingest.process_bid_email(
        message_id="msg-001",
        subject="Bid request - Willow Creek Ph2 lots 41-46",
        body="(body)",
        repo=repo,
    )

    assert result.created == 6
    assert len(repo.bids) == 6
    assert {f[at.F_LOT] for f in repo.bids.values()} == {
        "Lot 41", "Lot 42", "Lot 43", "Lot 44", "Lot 45", "Lot 46"
    }
    assert all(f[at.F_STATUS] == Stage.BID_REQUEST.value for f in repo.bids.values())
    assert result.cost_usd == pytest.approx(USAGE.cost_usd)


def test_replaying_the_same_email_creates_nothing_and_costs_nothing(
    repo, stub_extraction
):
    """Zapier retries on any non-2xx. A retry must be free as well as harmless
    -- hence the idempotency check ahead of the model call, not after it."""
    calls = stub_extraction(_six_lot_batch())

    ingest.process_bid_email(
        message_id="msg-001", subject="s", body="b", repo=repo
    )
    assert calls["count"] == 1

    replay = ingest.process_bid_email(
        message_id="msg-001", subject="s", body="b", repo=repo
    )

    assert len(repo.bids) == 6, "replay must not create a seventh record"
    assert replay.created == 0
    assert calls["count"] == 1, "replay must not call the model again"
    assert replay.cost_usd == 0.0


def test_each_record_gets_its_own_idempotency_key(repo, stub_extraction):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    keys = {f[at.F_IDEMPOTENCY] for f in repo.bids.values()}
    assert len(keys) == 6


# --- revisions ----------------------------------------------------------


def test_a_revision_updates_in_place_rather_than_duplicating(repo, stub_extraction):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    revision = BidRequestBatch(
        intent=EmailIntent.REVISION,
        summary="Lot 42 scope revised.",
        bids=[
            ExtractedBid(
                property_name="Willow Creek Phase 2",
                lot_number="Lot 42",
                scope_of_work="R&R carpet, pad AND subfloor repair",
                confidence=0.95,
            )
        ],
    )
    stub_extraction(revision)

    result = ingest.process_bid_email(
        message_id="msg-002", subject="RE: revised", body="b", repo=repo
    )

    assert result.updated == 1
    assert len(repo.bids) == 6, "a revision must not create a seventh record"

    revised = next(f for f in repo.bids.values() if f[at.F_LOT] == "Lot 42")
    assert "subfloor" in revised[at.F_SCOPE]

    # The old value has to survive somewhere, or the revision is not reversible.
    logged = [e for e in repo.run_log if e.get("event") == "bid_revised"]
    assert logged and "R&R carpet and pad throughout" in str(
        logged[0]["changed_fields"]
    )


def test_cancellation_flags_and_never_deletes(repo, stub_extraction):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)
    before = len(repo.bids)

    stub_extraction(
        BidRequestBatch(
            intent=EmailIntent.CANCELLATION,
            summary="Lot 44 cancelled.",
            bids=[
                ExtractedBid(
                    property_name="Willow Creek Phase 2",
                    lot_number="Lot 44",
                    scope_of_work="R&R carpet and pad throughout",
                    confidence=0.98,
                )
            ],
        )
    )
    result = ingest.process_bid_email(
        message_id="msg-003", subject="cancel lot 44", body="b", repo=repo
    )

    assert len(repo.bids) == before, "nothing may be deleted"
    assert result.flagged == 1, "cancellation is queued, not auto-applied"

    lot44 = next(f for f in repo.bids.values() if f[at.F_LOT] == "Lot 44")
    assert lot44[at.F_STATUS] != Stage.CANCELLED.value, (
        "status must not change until a human confirms"
    )
    assert lot44[at.F_NEEDS_REVIEW] is True


def test_low_confidence_lands_in_the_queue_rather_than_being_dropped(
    repo, stub_extraction
):
    stub_extraction(
        BidRequestBatch(
            intent=EmailIntent.NEW_REQUEST,
            summary="Barely legible forwarded scan.",
            bids=[
                ExtractedBid(
                    property_name="Harbor Point",
                    lot_number="7",
                    scope_of_work="unclear",
                    confidence=0.42,
                )
            ],
        )
    )

    result = ingest.process_bid_email(
        message_id="msg-004", subject="fwd", body="b", repo=repo
    )

    assert result.flagged == 1
    assert len(repo.bids) == 1, "a flagged item is parked in the base, not dropped"
    parked = next(iter(repo.bids.values()))
    assert parked[at.F_NEEDS_REVIEW] is True
    assert "42%" in parked[at.F_REVIEW_REASON]


# --- purchase orders ----------------------------------------------------


def _stub_po(monkeypatch, po: ExtractedPurchaseOrder):
    monkeypatch.setattr(
        ingest,
        "extract_purchase_order",
        lambda **_kw: ExtractionResult(parsed=po, usage=USAGE),
    )


def test_po_matches_existing_bid_and_computes_the_deposit(
    repo, stub_extraction, monkeypatch
):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    _stub_po(
        monkeypatch,
        ExtractedPurchaseOrder(
            po_number="PO-10045",
            property_name="Willow Creek Phase 2",
            lot_number="42",
            approved_amount=12_500.00,
            confidence=0.96,
        ),
    )

    result = ingest.process_purchase_order(
        message_id="po-msg-1", subject="PO attached", body="see attached", repo=repo
    )

    assert result.created == 1
    assert len(repo.bids) == 6, "a PO must attach to a bid, never create a job"

    po_record = next(iter(repo.purchase_orders.values()))
    assert po_record[at.F_PO_DEPOSIT] == 6_250.00
    assert po_record[at.F_NEEDS_REVIEW] is False

    matched = repo.bids[po_record[at.F_PO_BID][0]]
    assert matched[at.F_LOT] == "Lot 42"
    assert matched[at.F_STATUS] == Stage.PO_RECEIVED.value


def test_unmatchable_po_is_queued_and_moves_no_bid(repo, stub_extraction, monkeypatch):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    _stub_po(
        monkeypatch,
        ExtractedPurchaseOrder(
            po_number="PO-99999",
            property_name="Somewhere Else Entirely",
            lot_number="3",
            approved_amount=8_000.00,
            confidence=0.95,
        ),
    )

    result = ingest.process_purchase_order(
        message_id="po-msg-2", body="x", repo=repo
    )

    assert result.flagged == 1
    assert all(
        f[at.F_STATUS] == Stage.BID_REQUEST.value for f in repo.bids.values()
    ), "an unmatched PO must not advance any bid"


def test_po_with_no_readable_amount_does_not_advance_the_pipeline(
    repo, stub_extraction, monkeypatch
):
    """A confident match is not enough: without the money there is no deposit
    to invoice, so the stage must not move."""
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    _stub_po(
        monkeypatch,
        ExtractedPurchaseOrder(
            po_number="PO-10046",
            property_name="Willow Creek Phase 2",
            lot_number="43",
            approved_amount=None,
            confidence=0.95,
            uncertain_fields=["approved_amount"],
        ),
    )

    result = ingest.process_purchase_order(message_id="po-msg-3", body="x", repo=repo)

    assert result.flagged == 1
    assert all(
        f[at.F_STATUS] == Stage.BID_REQUEST.value for f in repo.bids.values()
    )


def test_replayed_po_creates_nothing(repo, stub_extraction, monkeypatch):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)
    _stub_po(
        monkeypatch,
        ExtractedPurchaseOrder(
            po_number="PO-10045",
            property_name="Willow Creek Phase 2",
            lot_number="42",
            approved_amount=12_500.00,
            confidence=0.96,
        ),
    )

    ingest.process_purchase_order(message_id="po-msg-1", body="x", repo=repo)
    ingest.process_purchase_order(message_id="po-msg-1", body="x", repo=repo)

    assert len(repo.purchase_orders) == 1


# --- audit --------------------------------------------------------------


def test_every_ingest_leaves_an_audit_trail_with_cost(repo, stub_extraction):
    stub_extraction(_six_lot_batch())
    ingest.process_bid_email(message_id="msg-001", subject="s", body="b", repo=repo)

    assert "bid_email_processed" in repo.events()
    summary = next(e for e in repo.run_log if e["event"] == "bid_email_processed")
    assert summary["usage"].cost_usd > 0
