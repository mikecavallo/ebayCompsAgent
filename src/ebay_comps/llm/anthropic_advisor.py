"""Claude-backed advisor using structured outputs (`messages.parse` with a Pydantic schema)."""

from __future__ import annotations

from typing import Any

from ebay_comps.llm.base import SYSTEM_PROMPT, AdvisorError, build_user_prompt
from ebay_comps.models import CompsStats, Condition, Listing, PricingRecommendation

DEFAULT_MODEL = "claude-sonnet-5-5"


class AnthropicAdvisor:
    def __init__(self, model: str = DEFAULT_MODEL, client: Any | None = None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self._client = client
        self.model = model
        self.name = f"anthropic:{model}"

    def recommend(
        self, query: str, condition: Condition, stats: CompsStats, comps: list[Listing]
    ) -> PricingRecommendation:
        # Server-side fallbacks ("default") re-route the request if a safety classifier
        # declines it, instead of failing outright. Supported on the first-party Claude API.
        response = self._client.beta.messages.parse(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": build_user_prompt(query, condition, stats, comps)}
            ],
            output_format=PricingRecommendation,
        )
        if response.stop_reason == "refusal":
            raise AdvisorError("Claude declined to produce a recommendation for this request.")
        if response.stop_reason == "max_tokens":
            raise AdvisorError("Claude's response was truncated (max_tokens).")
        if response.parsed_output is None:
            raise AdvisorError("Claude returned no structured recommendation.")
        return response.parsed_output
