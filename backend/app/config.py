"""Runtime configuration.

Everything is environment-driven so the same image runs locally, in CI (with no
credentials at all), and in production.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Anthropic -------------------------------------------------------
    anthropic_api_key: str = ""
    # Opus 5 is the extraction engine. $5/MTok in, $25/MTok out.
    extraction_model: str = "claude-opus-5"
    extraction_max_tokens: int = 8000
    # Thinking is on by default on Opus 5. Extraction is a reading task, not a
    # reasoning one, and Opus 5's lower effort levels are unusually strong --
    # "medium" keeps the per-email cost line honest without measurable
    # accuracy loss on the fixtures. Raise to "high" if recall drops on real
    # mail.
    extraction_effort: str = "medium"

    # --- Airtable --------------------------------------------------------
    airtable_api_key: str = ""
    airtable_base_id: str = ""

    # --- Webhook auth ----------------------------------------------------
    # Zapier signs each webhook body with this secret; see app/security.py.
    webhook_secret: str = ""
    # Local development convenience. Never enable in production.
    allow_unsigned_webhooks: bool = False

    # --- Matching thresholds --------------------------------------------
    # Below this, a PO->bid match is never applied automatically.
    match_auto_apply_threshold: float = 0.90
    # Below this a candidate is not even offered for review.
    match_candidate_threshold: float = 0.60
    # Below this, an extracted field is flagged for human review.
    extraction_confidence_threshold: float = 0.80

    # Origins the dashboard may be served from. Comma-separated in the
    # environment. Needs to be configurable rather than hardcoded to the dev
    # port: the deployed dashboard is on a real domain, and a demo is often on
    # whatever port happens to be free.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Serve an in-memory base seeded with plausible data instead of talking to
    # Airtable. Lets the dashboard be demonstrated and recorded without
    # credentials. Reported by /health so a service left in this state is
    # visible rather than silently serving fiction.
    demo_mode: bool = False

    # A cancellation is NEVER auto-applied regardless of confidence. This flag
    # exists so the behaviour is a visible, deliberate decision rather than an
    # accident of omission. See docs/joist-assessment.md and the architecture
    # explorer's `auto-cancel` node.
    enable_auto_cancellation: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
