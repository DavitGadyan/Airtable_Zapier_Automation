"""Deterministic identity for a job.

Three distinct keys, doing three distinct jobs. Conflating them is how systems
like this end up either creating duplicates or overwriting live records:

  job_fingerprint   -- which physical job is this? (property + lot)
                       Stable across revisions: a revised scope is the same job.
  content_hash      -- have I seen these exact field values before?
                       Detects a re-sent identical email -> no-op.
  idempotency_key   -- have I processed this exact delivery before?
                       Survives Zapier retries and Gmail redelivery.

Normalisation here is deliberately strict: case, punctuation and whitespace
only. It never guesses that "Willow Creek" and "Willow Creek Estates" are the
same place. All tolerance for human variation lives one layer up, in fuzzy
matching, where it produces a score and a review path rather than a silent
merge.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")

# "Lot 42", "L-42", "#42", "Unit 12B" all denote the same lot as "42"/"12b".
# Anchored and applied once, so a genuine lot named "A1" is left alone.
_LOT_PREFIX = re.compile(r"^(?:lot|unit|lt|no|num|l|u)")


def _strip_accents(value: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def normalize_property(value: str | None) -> str:
    """Case, accent and whitespace normalisation. Nothing else.

    Notably does NOT drop tokens like "Subdivision", "Estates" or "Phase 2":
    "Willow Creek Phase 2" and "Willow Creek Phase 3" are different
    developments with near-identical lot numbering, and collapsing them would
    cross-wire two jobs permanently.
    """
    if not value:
        return ""
    text = _strip_accents(value).lower().strip()
    text = _NON_ALNUM.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def normalize_lot(value: str | None) -> str:
    """Reduce a lot identifier to its significant characters.

    >>> normalize_lot("Lot 42"), normalize_lot("L-42"), normalize_lot("#42")
    ('42', '42', '42')
    >>> normalize_lot("Unit 12B")
    '12b'
    """
    if not value:
        return ""
    text = _strip_accents(value).lower()
    text = _NON_ALNUM.sub("", text)
    stripped = _LOT_PREFIX.sub("", text, count=1)
    # Only accept the prefix strip if something meaningful survives; otherwise
    # the "lot" WAS the identifier and we keep it verbatim.
    return stripped if stripped else text


def job_fingerprint(property_name: str | None, lot_number: str | None) -> str:
    """Stable identity for one physical job.

    Unchanged when the scope, due date, estimator or price is revised -- which
    is exactly what makes revision handling safe: a revision resolves to the
    same fingerprint and therefore updates in place instead of creating a
    second record for the same lot.
    """
    key = f"{normalize_property(property_name)}|{normalize_lot(lot_number)}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def content_hash(**fields: object) -> str:
    """Hash of the extracted field values.

    Keys are sorted so the digest does not depend on dict ordering -- an
    unsorted serialisation would make every re-send look like a change.
    """
    parts = [f"{k}={fields[k]!r}" for k in sorted(fields)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def idempotency_key(message_id: str, sequence: int = 0) -> str:
    """One key per (email, extracted record).

    Zapier retries a failed step and Gmail can redeliver; both replay the same
    message id. The sequence disambiguates the six bids that came out of one
    six-lot email, so a retry re-derives exactly the same six keys and creates
    nothing new.
    """
    return hashlib.sha256(f"{message_id}#{sequence}".encode()).hexdigest()[:16]
