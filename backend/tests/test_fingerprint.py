"""Fingerprinting: the deterministic layer everything else trusts.

If these break, revisions silently become duplicates. They are cheap tests
guarding an expensive failure.
"""

from __future__ import annotations

import pytest

from app.matching.fingerprint import (
    content_hash,
    idempotency_key,
    job_fingerprint,
    normalize_lot,
    normalize_property,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Lot 42", "42"),
        ("lot42", "42"),
        ("L-42", "42"),
        ("#42", "42"),
        ("  42  ", "42"),
        ("Unit 12B", "12b"),
        ("12B", "12b"),
        ("A1", "a1"),  # 'A' is not a lot prefix; left intact
        (None, ""),
        ("", ""),
    ],
)
def test_lot_normalisation(raw, expected):
    assert normalize_lot(raw) == expected


def test_lot_prefix_strip_never_empties_the_identifier():
    # "Lot" with no number is the identifier itself -- stripping the prefix
    # would leave nothing and collapse every such record onto one fingerprint.
    assert normalize_lot("Lot") == "lot"


@pytest.mark.parametrize(
    "a,b",
    [
        ("Willow Creek", "willow creek"),
        ("Willow  Creek", "Willow Creek"),
        ("Willow-Creek", "Willow Creek"),
        ("Cañada Hills", "Canada Hills"),
    ],
)
def test_property_normalisation_equivalences(a, b):
    assert normalize_property(a) == normalize_property(b)


def test_property_normalisation_keeps_meaningful_tokens():
    """Phase 2 and Phase 3 are different developments with overlapping lot
    numbering. Collapsing them would cross-wire two jobs permanently."""
    assert normalize_property("Willow Creek Phase 2") != normalize_property(
        "Willow Creek Phase 3"
    )
    assert normalize_property("Willow Creek") != normalize_property(
        "Willow Creek Estates"
    )


def test_fingerprint_is_stable_across_lot_formatting():
    assert job_fingerprint("Willow Creek", "Lot 42") == job_fingerprint(
        "willow creek", "42"
    )


def test_fingerprint_distinguishes_lots():
    assert job_fingerprint("Willow Creek", "42") != job_fingerprint(
        "Willow Creek", "43"
    )


def test_fingerprint_survives_a_scope_revision():
    """The whole revision story rests on this: change the scope, and it is
    still the same job."""
    before = job_fingerprint("Willow Creek", "Lot 42")
    after = job_fingerprint("Willow Creek", "Lot 42")
    assert before == after


def test_content_hash_is_order_independent():
    assert content_hash(a="1", b="2") == content_hash(b="2", a="1")


def test_content_hash_detects_a_real_change():
    assert content_hash(scope="carpet") != content_hash(scope="carpet and pad")


def test_idempotency_keys_are_unique_per_record_and_stable_on_replay():
    first_pass = [idempotency_key("msg-abc", i) for i in range(6)]
    replay = [idempotency_key("msg-abc", i) for i in range(6)]

    assert len(set(first_pass)) == 6, "six lots from one email need six keys"
    assert first_pass == replay, "a Zapier retry must re-derive the same keys"
    assert idempotency_key("msg-abc", 0) != idempotency_key("msg-xyz", 0)
