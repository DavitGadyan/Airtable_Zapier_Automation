"""Anthropic client plumbing shared by every extractor.

One place that knows how to call the model, so cost accounting, caching and
error handling are not reimplemented three times.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Published Claude API list pricing, USD per million tokens.
# https://platform.claude.com/docs/en/about-claude/models/overview
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


@dataclass(frozen=True)
class Usage:
    """Token usage and derived cost for a single extraction call.

    Written to the Run Log so the client can audit what the system actually
    costs rather than taking our word for it.
    """

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str

    @property
    def cost_usd(self) -> float:
        """Cost in USD, derived from published list pricing.

        Cache reads bill at ~0.1x input, cache writes at ~1.25x.
        """
        rate_in, rate_out = PRICING_PER_MTOK.get(self.model, (5.00, 25.00))
        million = 1_000_000
        return round(
            (self.input_tokens / million) * rate_in
            + (self.cache_read_tokens / million) * rate_in * 0.10
            + (self.cache_write_tokens / million) * rate_in * 1.25
            + (self.output_tokens / million) * rate_out,
            6,
        )


@dataclass(frozen=True)
class ExtractionResult:
    """A parsed model plus what it cost to produce."""

    parsed: Any
    usage: Usage


@lru_cache
def get_client() -> anthropic.Anthropic:
    """A bare constructor also picks up an `ant auth login` profile or
    ANTHROPIC_AUTH_TOKEN, so an unset ANTHROPIC_API_KEY is not fatal."""
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()


def _usage_from_response(response: Any, model: str) -> Usage:
    usage = response.usage
    return Usage(
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
        model=model,
    )


def extract(
    *,
    system: str,
    content: list[dict[str, Any]] | str,
    output_format: type[T],
) -> ExtractionResult:
    """Run one structured extraction.

    `system` is cached: it is a stable module-level constant, and the volatile
    per-request `content` comes after it, which is the ordering that makes the
    cache hit at all.
    """
    settings = get_settings()
    client = get_client()

    response = client.messages.parse(
        model=settings.extraction_model,
        max_tokens=settings.extraction_max_tokens,
        output_config={"effort": settings.extraction_effort},
        system=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": content}],
        output_format=output_format,
    )

    # Claude Opus 5 ships elevated safety classifiers and can decline with a
    # normal HTTP 200. Reading .parsed_output without checking would raise an
    # opaque AttributeError several frames away from the cause.
    if response.stop_reason == "refusal":
        detail = getattr(response, "stop_details", None)
        raise ExtractionRefused(
            f"model declined this document "
            f"(category={getattr(detail, 'category', None)})"
        )

    usage = _usage_from_response(response, settings.extraction_model)
    logger.info(
        "extraction ok model=%s in=%d out=%d cost=$%.4f",
        usage.model,
        usage.input_tokens,
        usage.output_tokens,
        usage.cost_usd,
    )
    return ExtractionResult(parsed=response.parsed_output, usage=usage)


class ExtractionRefused(RuntimeError):
    """The model declined to process the document.

    Routed to the review queue like any other low-confidence result rather
    than retried -- retrying an identical refused request just refuses again.
    """
