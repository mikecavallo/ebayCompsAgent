"""OpenAI-backed advisor using the Responses API with a Pydantic `text_format`."""

from __future__ import annotations

from typing import Any

from ebay_comps.llm.base import SYSTEM_PROMPT, AdvisorError, build_user_prompt
from ebay_comps.models import CompsStats, Condition, Listing, PricingRecommendation

DEFAULT_MODEL = "gpt-5"


class OpenAIAdvisor:
    def __init__(self, model: str = DEFAULT_MODEL, client: Any | None = None):
        if client is None:
            try:
                import openai
            except ImportError as exc:  # optional extra
                raise AdvisorError(
                    'OpenAI support needs: pip install "ebay-comps[openai]"'
                ) from exc
            client = openai.OpenAI()
        self._client = client
        self.model = model
        self.name = f"openai:{model}"

    def recommend(
        self, query: str, condition: Condition, stats: CompsStats, comps: list[Listing]
    ) -> PricingRecommendation:
        response = self._client.responses.parse(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=build_user_prompt(query, condition, stats, comps),
            text_format=PricingRecommendation,
        )
        if response.output_parsed is None:
            raise AdvisorError("OpenAI returned no structured recommendation.")
        return response.output_parsed
