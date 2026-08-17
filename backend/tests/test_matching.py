"""PO -> bid matching.

`allow_llm=False` throughout: tier 3 is the only part that costs money, and
these tests assert the behaviour of the two free tiers plus the guard rails
that decide when tier 3 is even reached.
"""

from __future__ import annotations

from app.matching.matcher import MatchMethod, match_purchase_order


def test_exact_fingerprint_match_auto_applies(po_factory, candidate_factory):
    result = match_purchase_order(
        po_factory(property_name="Willow Creek", lot_number="42"),
        [candidate_factory(record_id="recA", property_name="Willow Creek", lot_number="Lot 42")],
        allow_llm=False,
    )
    assert result.bid_id == "recA"
    assert result.method is MatchMethod.EXACT
    assert result.score == 1.0
    assert result.needs_review is False


def test_typo_in_property_still_matches_via_fuzzy(po_factory, candidate_factory):
    """The client's PMs write 'Willow Crk'. That must not create a second job."""
    result = match_purchase_order(
        po_factory(property_name="Willow Crk", lot_number="42"),
        [candidate_factory(record_id="recA", property_name="Willow Creek", lot_number="Lot 42")],
        allow_llm=False,
    )
    assert result.bid_id == "recA"
    assert result.method is MatchMethod.FUZZY
    assert result.needs_review is False


def test_wrong_lot_is_not_matched(po_factory, candidate_factory):
    """A lot mismatch is close to disqualifying however well the rest lines up."""
    result = match_purchase_order(
        po_factory(property_name="Willow Creek", lot_number="99"),
        [
            candidate_factory(
                record_id="recA",
                property_name="Willow Creek",
                lot_number="Lot 42",
                scope_of_work="R&R carpet throughout",
            )
        ],
        allow_llm=False,
    )
    assert result.needs_review is True
    assert result.bid_id is None or result.score < 0.90


def test_no_open_bids_is_flagged_not_guessed(po_factory):
    result = match_purchase_order(po_factory(), [], allow_llm=False)
    assert result.bid_id is None
    assert result.method is MatchMethod.NONE
    assert result.needs_review is True


def test_two_bids_on_the_same_lot_refuse_to_guess(po_factory, candidate_factory):
    """Duplicate open bids on one lot is a data problem in the base. Picking
    one at random would bury it."""
    result = match_purchase_order(
        po_factory(property_name="Willow Creek", lot_number="42"),
        [
            candidate_factory(record_id="recA"),
            candidate_factory(record_id="recB"),
        ],
        allow_llm=False,
    )
    assert result.bid_id is None
    assert result.needs_review is True
    assert "human" in result.reasoning.lower()


def test_near_tie_does_not_auto_apply(po_factory, candidate_factory):
    """Two phases of one subdivision, same lot number, PO names neither phase.

    Both score highly and almost identically. The margin rule is what stops
    this landing on a coin-flip -- exactly the case that attaches money to the
    wrong job.
    """
    result = match_purchase_order(
        po_factory(property_name="Willow Creek", lot_number="42"),
        [
            candidate_factory(
                record_id="recA", property_name="Willow Creek Phase 2", lot_number="Lot 42"
            ),
            candidate_factory(
                record_id="recB", property_name="Willow Creek Phase 3", lot_number="Lot 42"
            ),
        ],
        allow_llm=False,
    )
    assert result.needs_review is True, "a near-tie must never auto-apply"


def test_missing_lot_on_the_po_forces_review(po_factory, candidate_factory):
    """Without a lot there is no discriminating signal, however good the
    property match is. A strong name match must not carry it through."""
    result = match_purchase_order(
        po_factory(property_name="Willow Creek", lot_number=None),
        [candidate_factory(record_id="recA", property_name="Willow Creek", lot_number="Lot 42")],
        allow_llm=False,
    )
    assert result.needs_review is True


def test_unrelated_po_is_not_forced_onto_a_bid(po_factory, candidate_factory):
    result = match_purchase_order(
        po_factory(property_name="Harbor Point", lot_number="7"),
        [candidate_factory(record_id="recA", property_name="Willow Creek", lot_number="Lot 42")],
        allow_llm=False,
    )
    assert result.bid_id is None
    assert result.method is MatchMethod.NONE
    assert result.needs_review is True


def test_scope_absence_does_not_penalise_an_otherwise_clean_match(
    po_factory, candidate_factory
):
    """Renormalisation check: a two-signal match should score as well as a
    three-signal one, not be dragged under the bar for lacking a third."""
    with_scope = match_purchase_order(
        po_factory(property_name="Willow Crk", lot_number="42", scope_of_work="carpet"),
        [
            candidate_factory(
                record_id="recA",
                property_name="Willow Creek",
                lot_number="Lot 42",
                scope_of_work="carpet",
            )
        ],
        allow_llm=False,
    )
    without_scope = match_purchase_order(
        po_factory(property_name="Willow Crk", lot_number="42"),
        [candidate_factory(record_id="recA", property_name="Willow Creek", lot_number="Lot 42")],
        allow_llm=False,
    )
    assert without_scope.needs_review == with_scope.needs_review is False
