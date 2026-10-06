"""Build listing sources and advisors from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping

from ebay_comps.llm import AnthropicAdvisor, MockAdvisor, OpenAIAdvisor
from ebay_comps.llm.anthropic_advisor import DEFAULT_MODEL as ANTHROPIC_DEFAULT
from ebay_comps.llm.base import Advisor
from ebay_comps.llm.openai_advisor import DEFAULT_MODEL as OPENAI_DEFAULT
from ebay_comps.providers import EbayApiSource, FixtureSource, ListingSource

SOURCES = ("auto", "ebay", "fixture")
LLMS = ("auto", "anthropic", "openai", "mock")


class ConfigError(RuntimeError):
    pass


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def make_source(kind: str = "auto", env: Mapping[str, str] | None = None) -> ListingSource:
    env = os.environ if env is None else env
    has_keys = bool(env.get("EBAY_CLIENT_ID") and env.get("EBAY_CLIENT_SECRET"))
    if kind == "auto":
        kind = "ebay" if has_keys else "fixture"
    if kind == "fixture":
        return FixtureSource()
    if kind == "ebay":
        if not has_keys:
            raise ConfigError("Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to use the eBay API.")
        return EbayApiSource(
            env["EBAY_CLIENT_ID"],
            env["EBAY_CLIENT_SECRET"],
            environment=env.get("EBAY_ENV", "production"),
            marketplace_id=env.get("EBAY_MARKETPLACE_ID", "EBAY_US"),
            use_insights=_truthy(env.get("EBAY_USE_MARKETPLACE_INSIGHTS")),
        )
    raise ConfigError(f"Unknown source {kind!r}; choose from {SOURCES}")


def make_advisor(kind: str = "auto", env: Mapping[str, str] | None = None) -> Advisor:
    env = os.environ if env is None else env
    if kind == "auto":
        if env.get("ANTHROPIC_API_KEY"):
            kind = "anthropic"
        elif env.get("OPENAI_API_KEY"):
            kind = "openai"
        else:
            kind = "mock"
    if kind == "anthropic":
        if not env.get("ANTHROPIC_API_KEY"):
            raise ConfigError("Set ANTHROPIC_API_KEY to use Claude.")
        return AnthropicAdvisor(model=env.get("ANTHROPIC_MODEL") or ANTHROPIC_DEFAULT)
    if kind == "openai":
        if not env.get("OPENAI_API_KEY"):
            raise ConfigError("Set OPENAI_API_KEY to use OpenAI.")
        return OpenAIAdvisor(model=env.get("OPENAI_MODEL") or OPENAI_DEFAULT)
    if kind == "mock":
        return MockAdvisor()
    raise ConfigError(f"Unknown LLM {kind!r}; choose from {LLMS}")
