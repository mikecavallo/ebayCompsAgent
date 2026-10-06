import pytest

from ebay_comps.llm import MockAdvisor
from ebay_comps.providers import FixtureSource

GBC = "Nintendo Game Boy Color console"


@pytest.fixture
def fixture_source():
    return FixtureSource()


@pytest.fixture
def mock_advisor():
    return MockAdvisor()


@pytest.fixture(autouse=True)
def _no_real_keys(monkeypatch):
    """Tests must never pick up real credentials from the developer's shell."""
    for key in (
        "EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        "AIRTABLE_API_KEY", "AIRTABLE_BASE_ID",
    ):  # fmt: skip
        monkeypatch.delenv(key, raising=False)
