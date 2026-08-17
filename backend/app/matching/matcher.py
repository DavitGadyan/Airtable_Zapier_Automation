"""Match an incoming purchase order to the bid it belongs to.

Three tiers, cheapest first. The tiering is the point: the LLM is the last
resort, not the first. On the fixture corpus the deterministic tier resolves
the clear majority of POs at zero marginal cost and zero latency, and the model
is consulted only for the genuinely ambiguous remainder -- which is also the
only place its judgement is worth paying for.

  Tier 1  exact job fingerprint      free, instant, unambiguous
  Tier 2  fuzzy property + lot       free, instant, scored
  Tier 3  LLM adjudication           ~$0.01, only when tier 2 is ambiguous

Failure is biased deliberately. An unmatched PO surfaces in a review queue and
costs one click. A wrongly matched PO attaches money and a deposit schedule to
the wrong job and is found weeks later, if at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz

from app.config import get_settings
from app.extraction.client import extract
from app.extraction.prompts import MATCH_ADJUDICATION_SYSTEM
from app.extraction.schemas import ExtractedPurchaseOrder, MatchAdjudication
from app.matching.fingerprint import job_fingerprint, normalize_lot, normalize_property

logger = logging.getLogger(__name__)


class MatchMethod(str, Enum):
    EXACT = "exact_fingerprint"
    FUZZY = "fuzzy"
    ADJUDICATED = "llm_adjudicated"
    NONE = "no_match"


@dataclass
class CandidateBid:
    """The subset of a bid record matching needs. Keeps this module testable
    without an Airtable connection."""

    record_id: str
    property_name: str
    lot_number: str | None
    scope_of_work: str | None = None
    status: str | None = None

    @property
    def fingerprint(self) -> str:
        return job_fingerprint(self.property_name, self.lot_number)


@dataclass
class MatchResult:
    bid_id: str | None
    score: float
    method: MatchMethod
    reasoning: str
    # True when a human must confirm before anything is written.
    needs_review: bool

    @property
    def matched(self) -> bool:
        return self.bid_id is not None


# Weight per signal. The lot dominates on purpose: adjacent lots in one
# subdivision share a property name and often a near-identical scope, so the
# lot number is usually the only field that actually tells them apart.
_W_LOT, _W_PROPERTY, _W_SCOPE = 0.50, 0.35, 0.15

# Score used when the lot cannot be compared because one side is missing it.
# Deliberately low but non-zero, and it keeps its full weight rather than being
# dropped: an unknown lot is not neutral evidence, it is the absence of the one
# signal that discriminates. Carrying it at full weight caps the achievable
# total below the auto-apply bar, which routes lot-less POs to a human instead
# of letting a strong property-name match carry them through.
_LOT_UNKNOWN = 0.30


def _fuzzy_score(po: ExtractedPurchaseOrder, bid: CandidateBid) -> float:
    """Weighted similarity in [0, 1], renormalised over available signals.

    Signals that cannot be compared at all (scope absent on either side) are
    dropped and the remaining weights renormalised, rather than being scored
    0.5. A neutral placeholder would drag a genuinely clean two-signal match
    below the auto-apply threshold purely for lacking a third.
    """
    po_lot = normalize_lot(po.lot_number)
    bid_lot = normalize_lot(bid.lot_number)
    if po_lot and bid_lot:
        lot_score = 1.0 if po_lot == bid_lot else 0.0
    else:
        lot_score = _LOT_UNKNOWN
    signals: list[tuple[float, float]] = [(_W_LOT, lot_score)]

    if po.property_name and bid.property_name:
        signals.append(
            (
                _W_PROPERTY,
                fuzz.token_sort_ratio(
                    normalize_property(po.property_name),
                    normalize_property(bid.property_name),
                )
                / 100.0,
            )
        )

    if po.scope_of_work and bid.scope_of_work:
        signals.append(
            (
                _W_SCOPE,
                fuzz.token_set_ratio(
                    po.scope_of_work.lower(), bid.scope_of_work.lower()
                )
                / 100.0,
            )
        )

    total_weight = sum(weight for weight, _ in signals)
    weighted = sum(weight * score for weight, score in signals)
    return round(weighted / total_weight, 4)


def _adjudicate(
    po: ExtractedPurchaseOrder, candidates: list[tuple[CandidateBid, float]]
) -> MatchResult:
    """Tier 3. Only reached when tier 2 left real ambiguity."""
    lines = [
        "<purchase_order>",
        f"  po_number: {po.po_number}",
        f"  property: {po.property_name}",
        f"  lot: {po.lot_number}",
        f"  scope: {po.scope_of_work}",
        f"  amount: {po.approved_amount}",
        "</purchase_order>",
        "<candidate_bids>",
    ]
    for bid, score in candidates:
        lines.append(
            f'  <bid id="{bid.record_id}" fuzzy_score="{score:.2f}">'
            f" property={bid.property_name!r} lot={bid.lot_number!r}"
            f" scope={bid.scope_of_work!r} status={bid.status!r} </bid>"
        )
    lines.append("</candidate_bids>")

    result = extract(
        system=MATCH_ADJUDICATION_SYSTEM,
        content="\n".join(lines),
        output_format=MatchAdjudication,
    )
    verdict: MatchAdjudication = result.parsed

    valid_ids = {bid.record_id for bid, _ in candidates}
    if verdict.chosen_bid_id and verdict.chosen_bid_id not in valid_ids:
        # Structured outputs guarantee the shape, not that the id was one we
        # offered. Treat an invented id as no match rather than writing to a
        # record that may not exist.
        logger.warning(
            "adjudicator returned unknown bid id %s; treating as no match",
            verdict.chosen_bid_id,
        )
        return MatchResult(
            bid_id=None,
            score=0.0,
            method=MatchMethod.NONE,
            reasoning="Adjudicator returned an id that was not among the candidates.",
            needs_review=True,
        )

    settings = get_settings()
    return MatchResult(
        bid_id=verdict.chosen_bid_id,
        score=verdict.confidence,
        method=MatchMethod.ADJUDICATED if verdict.chosen_bid_id else MatchMethod.NONE,
        reasoning=verdict.reasoning,
        # An adjudicated match always gets a human look unless it is emphatic.
        needs_review=(
            verdict.chosen_bid_id is None
            or verdict.confidence < settings.match_auto_apply_threshold
        ),
    )


def match_purchase_order(
    po: ExtractedPurchaseOrder,
    candidates: list[CandidateBid],
    *,
    allow_llm: bool = True,
) -> MatchResult:
    """Resolve `po` to one of `candidates`, or to nothing.

    `allow_llm=False` short-circuits tier 3, used by the offline test suite and
    available as a kill switch if the client wants a zero-inference path.
    """
    settings = get_settings()

    if not candidates:
        return MatchResult(
            bid_id=None,
            score=0.0,
            method=MatchMethod.NONE,
            reasoning="No open bids to match against.",
            needs_review=True,
        )

    # --- Tier 1: exact job fingerprint ---------------------------------
    po_fingerprint = job_fingerprint(po.property_name, po.lot_number)
    if po.property_name and po.lot_number:
        exact = [b for b in candidates if b.fingerprint == po_fingerprint]
        if len(exact) == 1:
            return MatchResult(
                bid_id=exact[0].record_id,
                score=1.0,
                method=MatchMethod.EXACT,
                reasoning="Property and lot match an existing bid exactly.",
                needs_review=False,
            )
        if len(exact) > 1:
            # Two open bids on the same lot is a data-quality problem in the
            # base, not something to resolve by picking one.
            return MatchResult(
                bid_id=None,
                score=0.0,
                method=MatchMethod.NONE,
                reasoning=(
                    f"{len(exact)} open bids share this property and lot. "
                    "Needs a human to say which is live."
                ),
                needs_review=True,
            )

    # --- Tier 2: fuzzy -------------------------------------------------
    scored = sorted(
        ((bid, _fuzzy_score(po, bid)) for bid in candidates),
        key=lambda pair: pair[1],
        reverse=True,
    )
    plausible = [
        (bid, score)
        for bid, score in scored
        if score >= settings.match_candidate_threshold
    ]

    if not plausible:
        return MatchResult(
            bid_id=None,
            score=scored[0][1] if scored else 0.0,
            method=MatchMethod.NONE,
            reasoning=(
                "No open bid resembles this PO. Most likely a bid that was "
                "never entered, or a PO for another contractor."
            ),
            needs_review=True,
        )

    best_bid, best_score = plausible[0]
    runner_up = plausible[1][1] if len(plausible) > 1 else 0.0

    # A clear winner: strong on its own AND clearly ahead of the next one.
    # The margin check matters more than the absolute score -- two lots in the
    # same subdivision both scoring 0.93 is precisely the dangerous case.
    if best_score >= settings.match_auto_apply_threshold and (
        best_score - runner_up
    ) >= 0.15:
        return MatchResult(
            bid_id=best_bid.record_id,
            score=best_score,
            method=MatchMethod.FUZZY,
            reasoning=(
                f"Closest open bid at {best_score:.0%}, next best "
                f"{runner_up:.0%}."
            ),
            needs_review=False,
        )

    # --- Tier 3: adjudication ------------------------------------------
    if allow_llm and len(plausible) > 1:
        logger.info(
            "PO %s ambiguous across %d candidates; adjudicating",
            po.po_number,
            len(plausible),
        )
        return _adjudicate(po, plausible[:5])

    return MatchResult(
        bid_id=best_bid.record_id,
        score=best_score,
        method=MatchMethod.FUZZY,
        reasoning=(
            f"Best candidate at {best_score:.0%}, below the "
            f"{settings.match_auto_apply_threshold:.0%} auto-apply bar."
        ),
        needs_review=True,
    )
