"""Revisions, additions and cancellations.

These tests are the executable form of the client's hardest requirement:
handle changes "without creating duplicates or accidentally deleting valid
bids". Each of the three safety rules has a test that fails loudly if someone
relaxes it later.
"""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.extraction.schemas import EmailIntent
from app.matching.revision import Action, classify, diff_fields


# --- new work -----------------------------------------------------------


def test_unknown_lot_creates(bid_factory):
    decision = classify(bid_factory(), EmailIntent.NEW_REQUEST, [])
    assert decision.action is Action.CREATE
    assert decision.auto_appliable


def test_additional_lot_on_known_property_creates_a_second_record(
    bid_factory, existing_factory
):
    """An 'addition' email is new work, not an edit of the existing lot."""
    decision = classify(
        bid_factory(lot_number="Lot 43"),
        EmailIntent.ADDITION,
        [existing_factory(record_id="recA", lot_number="Lot 42")],
    )
    assert decision.action is Action.CREATE
    assert decision.target_bid_id is None


# --- duplicates ---------------------------------------------------------


def test_identical_resend_is_a_no_op(bid_factory, existing_factory):
    """The duplicate-prevention requirement, in one test."""
    decision = classify(
        bid_factory(scope="R&R carpet throughout"),
        EmailIntent.NEW_REQUEST,
        [existing_factory(scope_of_work="R&R carpet throughout")],
    )
    assert decision.action is Action.NO_OP
    assert decision.target_bid_id == "recBID001"


def test_reformatted_lot_still_resolves_to_the_same_job(
    bid_factory, existing_factory
):
    """'42' and 'Lot 42' are the same lot. Treating them as different is how
    duplicates are born."""
    decision = classify(
        bid_factory(lot_number="42", scope="R&R carpet throughout"),
        EmailIntent.NEW_REQUEST,
        [existing_factory(lot_number="Lot 42", scope_of_work="R&R carpet throughout")],
    )
    assert decision.action is Action.NO_OP


def test_ambiguous_duplicate_in_the_base_goes_to_review(bid_factory, existing_factory):
    decision = classify(
        bid_factory(),
        EmailIntent.REVISION,
        [existing_factory(record_id="recA"), existing_factory(record_id="recB")],
    )
    assert decision.action is Action.REVIEW
    assert decision.requires_confirmation


# --- revisions ----------------------------------------------------------


def test_revision_updates_in_place_and_records_the_old_value(
    bid_factory, existing_factory
):
    decision = classify(
        bid_factory(scope="R&R carpet and pad throughout"),
        EmailIntent.REVISION,
        [existing_factory(scope_of_work="R&R carpet throughout")],
    )
    assert decision.action is Action.UPDATE
    assert decision.target_bid_id == "recBID001"
    assert decision.changed_fields["scope_of_work"]["from"] == "R&R carpet throughout"
    assert decision.changed_fields["scope_of_work"]["to"] == "R&R carpet and pad throughout"
    assert decision.auto_appliable


def test_revision_against_a_committed_bid_needs_confirmation(
    bid_factory, existing_factory
):
    """Once a PO is attached, the scope this would rewrite has already been
    priced and accepted. That is a person's call."""
    decision = classify(
        bid_factory(scope="Now also replace subfloor"),
        EmailIntent.REVISION,
        [existing_factory(status="Deposit Paid", scope_of_work="R&R carpet throughout")],
    )
    assert decision.action is Action.UPDATE
    assert decision.requires_confirmation is True
    assert not decision.auto_appliable


def test_omitted_field_is_not_treated_as_a_deletion(bid_factory, existing_factory):
    """A follow-up email that does not repeat the due date is not asking for
    the due date to be cleared."""
    incoming = bid_factory(scope="R&R carpet throughout")
    incoming.bid_due_date = None
    changes = diff_fields(
        incoming,
        existing_factory(scope_of_work="R&R carpet throughout", bid_due_date="2026-09-01"),
    )
    assert "bid_due_date" not in changes


def test_revision_to_a_closed_bid_is_not_applied_silently(
    bid_factory, existing_factory
):
    decision = classify(
        bid_factory(scope="One more thing"),
        EmailIntent.REVISION,
        [existing_factory(status="Closed")],
    )
    assert decision.action is Action.REVIEW
    assert decision.requires_confirmation


# --- cancellations ------------------------------------------------------


def test_cancellation_never_deletes(bid_factory, existing_factory):
    decision = classify(
        bid_factory(), EmailIntent.CANCELLATION, [existing_factory()]
    )
    assert decision.action is Action.CANCEL
    assert decision.target_bid_id == "recBID001"


def test_cancellation_does_not_auto_apply_by_default(bid_factory, existing_factory):
    """The deliberate limitation. A misread cancellation kills a live job and
    is not recoverable from the email thread alone."""
    decision = classify(
        bid_factory(confidence=0.99), EmailIntent.CANCELLATION, [existing_factory()]
    )
    assert decision.requires_confirmation is True
    assert not decision.auto_appliable


def test_committed_cancellation_needs_confirmation_even_when_the_flag_is_on(
    monkeypatch: pytest.MonkeyPatch, bid_factory, existing_factory
):
    """The override exists, but it never reaches a job with money attached."""
    monkeypatch.setenv("ENABLE_AUTO_CANCELLATION", "true")
    get_settings.cache_clear()

    open_bid = classify(
        bid_factory(), EmailIntent.CANCELLATION, [existing_factory(status="Bid Request")]
    )
    assert open_bid.requires_confirmation is False, "flag should apply to open bids"

    committed = classify(
        bid_factory(), EmailIntent.CANCELLATION, [existing_factory(status="Deposit Paid")]
    )
    assert committed.requires_confirmation is True


def test_cancelling_something_we_never_captured_goes_to_review(bid_factory):
    decision = classify(bid_factory(), EmailIntent.CANCELLATION, [])
    assert decision.action is Action.REVIEW
    assert decision.requires_confirmation


# --- confidence gate ----------------------------------------------------


def test_low_confidence_never_auto_applies(bid_factory):
    decision = classify(bid_factory(confidence=0.55), EmailIntent.NEW_REQUEST, [])
    assert decision.action is Action.REVIEW
    assert decision.requires_confirmation
    assert "55%" in decision.reason


def test_uncertain_fields_are_named_in_the_review_reason(bid_factory):
    bid = bid_factory(confidence=0.4)
    bid.uncertain_fields = ["lot_number", "bid_due_date"]
    decision = classify(bid, EmailIntent.NEW_REQUEST, [])
    assert "lot_number" in decision.reason


def test_senders_framing_does_not_override_database_state(bid_factory):
    """A PM writes 'revised scope below' for a bid nobody ever entered. That
    is a new bid, whatever they called it."""
    decision = classify(bid_factory(), EmailIntent.REVISION, [])
    assert decision.action is Action.CREATE
