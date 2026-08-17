"""Pipeline stages, deposit arithmetic, and the cost model.

The cost figures quoted to the client come out of Usage.cost_usd, so it is
worth a test. A number a client checks and disproves discredits every other
number in the proposal.
"""

from __future__ import annotations

import pytest

from app.airtable.schema import TABLES, TABLES_BY_NAME
from app.extraction.client import PRICING_PER_MTOK, Usage
from app.pipeline import (
    ORDERED_STAGES,
    Stage,
    deposit_amount,
    is_committed,
    is_terminal,
)


def test_the_client_pipeline_is_reproduced_in_order():
    """The 14 stages, exactly as the client described their own process."""
    expected = [
        "Bid Request",
        "Bid Assigned",
        "Bid Submitted",
        "PO Received",
        "Deposit Invoice Sent",
        "Deposit Paid",
        "Crew Assigned",
        "Materials Ordered",
        "Scheduled",
        "In Progress",
        "Completed",
        "Final Invoice Sent",
        "Final Payment Received",
        "Closed",
    ]
    assert [s.value for s in ORDERED_STAGES][:14] == expected


def test_cancelled_is_a_status_not_a_deletion():
    assert Stage.CANCELLED in set(ORDERED_STAGES)
    assert is_terminal(Stage.CANCELLED)


@pytest.mark.parametrize(
    "stage,committed",
    [
        (Stage.BID_REQUEST, False),
        (Stage.BID_SUBMITTED, False),
        (Stage.PO_RECEIVED, True),
        (Stage.DEPOSIT_PAID, True),
        (Stage.IN_PROGRESS, True),
        (Stage.CLOSED, False),  # terminal, not "committed and still editable"
    ],
)
def test_committed_stages(stage, committed):
    assert is_committed(stage) is committed


def test_unknown_status_is_not_treated_as_committed():
    """A hand-typed status in Airtable must not silently unlock auto-edits."""
    assert is_committed("Waiting on Bob") is False
    assert is_terminal("Waiting on Bob") is False


def test_deposit_is_half_rounded_to_cents():
    assert deposit_amount(12500.00) == 6250.00
    assert deposit_amount(9999.99) == 5000.00  # .995 rounds to cents
    assert deposit_amount(0.0) == 0.0


# --- cost model ---------------------------------------------------------


def test_opus_5_pricing_matches_published_rates():
    assert PRICING_PER_MTOK["claude-opus-5"] == (5.00, 25.00)


def test_cost_arithmetic_is_checkable_by_hand():
    """3,000 in + 1,000 out on Opus 5:
    3000/1e6 * $5  = $0.015
    1000/1e6 * $25 = $0.025
                   = $0.040
    """
    usage = Usage(
        input_tokens=3_000,
        output_tokens=1_000,
        cache_read_tokens=0,
        cache_write_tokens=0,
        model="claude-opus-5",
    )
    assert usage.cost_usd == pytest.approx(0.040)


def test_cached_input_bills_at_a_tenth():
    cached = Usage(
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=1_000_000,
        cache_write_tokens=0,
        model="claude-opus-5",
    )
    assert cached.cost_usd == pytest.approx(0.50)


def test_unknown_model_falls_back_rather_than_crashing():
    usage = Usage(1000, 1000, 0, 0, "claude-something-new")
    assert usage.cost_usd > 0


# --- schema -------------------------------------------------------------


def test_base_has_the_nine_documented_tables():
    assert len(TABLES) == 9
    assert "Run Log" in TABLES_BY_NAME, "the audit trail is not optional"


def test_every_link_points_at_a_real_table():
    for table in TABLES:
        for link in table.links:
            assert link.to_table in TABLES_BY_NAME, (
                f"{table.name}.{link.name} -> unknown table {link.to_table}"
            )


def test_status_select_offers_every_pipeline_stage():
    status_field = next(
        f for f in TABLES_BY_NAME["Bids"].fields if f.name == "Status"
    )
    choices = {c["name"] for c in status_field.options["choices"]}
    assert choices == {s.value for s in ORDERED_STAGES}


def test_primary_field_is_a_text_field_in_every_table():
    """Airtable rejects links, checkboxes and attachments as the primary
    field. Getting this wrong fails provisioning at table 3 of 9."""
    for table in TABLES:
        assert table.fields[0].type in {"singleLineText", "multilineText"}, (
            f"{table.name}: primary field is {table.fields[0].type}"
        )
