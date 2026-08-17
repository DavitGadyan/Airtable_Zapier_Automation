"""Shared test fixtures.

The whole default suite runs offline: no ANTHROPIC_API_KEY, no AIRTABLE_API_KEY,
no network. That is a deliberate constraint, not a convenience -- it means the
extraction contract, the matching tiers and the safety rules are all verifiable
in CI and by anyone who clones the repo, without credentials or spend.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.config import get_settings
from app.extraction.schemas import ExtractedBid, ExtractedPurchaseOrder
from app.matching.matcher import CandidateBid
from app.matching.revision import ExistingBid

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch):
    """Pin settings to documented defaults and clear the lru_cache.

    Without the cache clear, the first test to call get_settings() would freeze
    that environment for the whole session and later monkeypatches would be
    silently ignored -- a failure mode that looks like a logic bug.
    """
    monkeypatch.setenv("MATCH_AUTO_APPLY_THRESHOLD", "0.90")
    monkeypatch.setenv("MATCH_CANDIDATE_THRESHOLD", "0.60")
    monkeypatch.setenv("EXTRACTION_CONFIDENCE_THRESHOLD", "0.80")
    monkeypatch.setenv("ENABLE_AUTO_CANCELLATION", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def load_email(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def bid_factory():
    def _make(
        property_name: str = "Willow Creek",
        lot_number: str | None = "Lot 42",
        scope: str = "R&R carpet throughout",
        confidence: float = 0.95,
        **overrides,
    ) -> ExtractedBid:
        return ExtractedBid(
            property_name=property_name,
            lot_number=lot_number,
            scope_of_work=scope,
            confidence=confidence,
            **overrides,
        )

    return _make


@pytest.fixture
def existing_factory():
    def _make(
        record_id: str = "recBID001",
        property_name: str = "Willow Creek",
        lot_number: str | None = "Lot 42",
        status: str | None = "Bid Request",
        **overrides,
    ) -> ExistingBid:
        return ExistingBid(
            record_id=record_id,
            property_name=property_name,
            lot_number=lot_number,
            status=status,
            **overrides,
        )

    return _make


@pytest.fixture
def po_factory():
    def _make(
        po_number: str = "PO-10045",
        property_name: str | None = "Willow Creek",
        lot_number: str | None = "42",
        amount: float | None = 12500.00,
        confidence: float = 0.95,
        **overrides,
    ) -> ExtractedPurchaseOrder:
        return ExtractedPurchaseOrder(
            po_number=po_number,
            property_name=property_name,
            lot_number=lot_number,
            approved_amount=amount,
            issue_date=date(2026, 8, 3),
            confidence=confidence,
            **overrides,
        )

    return _make


@pytest.fixture
def candidate_factory():
    def _make(
        record_id: str = "recBID001",
        property_name: str = "Willow Creek",
        lot_number: str | None = "Lot 42",
        **overrides,
    ) -> CandidateBid:
        return CandidateBid(
            record_id=record_id,
            property_name=property_name,
            lot_number=lot_number,
            **overrides,
        )

    return _make
