from types import SimpleNamespace

import pytest

from ebay_comps.agent import run_comps
from ebay_comps.llm import AdvisorError, AnthropicAdvisor, OpenAIAdvisor
from ebay_comps.llm.base import SYSTEM_PROMPT
from ebay_comps.models import PricingRecommendation

from .conftest import GBC

REC = PricingRecommendation(
    recommended_price=74.99, quick_sale_price=66.99, price_range_low=67.0,
    price_range_high=79.0, confidence="high", reasoning="Median of sold comps.",
)  # fmt: skip


class FakeAnthropic:
    def __init__(self, stop_reason="end_turn", parsed=REC):
        self.calls = []
        outer = self

        class Messages:
            def parse(self, **kwargs):
                outer.calls.append(kwargs)
                return SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)

        self.beta = SimpleNamespace(messages=Messages())


class FakeOpenAI:
    def __init__(self, parsed=REC):
        self.calls = []
        outer = self

        class Responses:
            def parse(self, **kwargs):
                outer.calls.append(kwargs)
                return SimpleNamespace(output_parsed=parsed)

        self.responses = Responses()


def test_anthropic_request_shape(fixture_source):
    client = FakeAnthropic()
    report = run_comps(GBC, fixture_source, AnthropicAdvisor(client=client))
    assert report.recommendation == REC
    assert report.llm == "anthropic:claude-sonnet-5-5"
    kwargs = client.calls[0]
    assert kwargs["model"] == "claude-sonnet-5-5"
    assert kwargs["output_format"] is PricingRecommendation
    assert kwargs["system"] == SYSTEM_PROMPT
    assert kwargs["fallbacks"] == "default"
    prompt = kwargs["messages"][0]["content"]
    assert GBC in prompt and '"sell_through"' in prompt and '"status": "sold"' in prompt


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_anthropic_bad_stop_reasons(fixture_source, stop):
    with pytest.raises(AdvisorError):
        run_comps(GBC, fixture_source, AnthropicAdvisor(client=FakeAnthropic(stop_reason=stop)))


def test_anthropic_missing_parse(fixture_source):
    with pytest.raises(AdvisorError):
        run_comps(GBC, fixture_source, AnthropicAdvisor(client=FakeAnthropic(parsed=None)))


def test_openai_request_shape(fixture_source):
    client = FakeOpenAI()
    report = run_comps(GBC, fixture_source, OpenAIAdvisor(model="gpt-test", client=client))
    assert report.recommendation == REC and report.llm == "openai:gpt-test"
    assert client.calls[0]["text_format"] is PricingRecommendation
    assert client.calls[0]["instructions"] == SYSTEM_PROMPT
