import json

import httpx
import pytest
import respx

from ebay_comps.providers.base import ProviderError
from ebay_comps.providers.ebay import EbayApiSource
from ebay_comps.providers.fixture import FIXTURE_DIR

HOST = "https://api.ebay.com"
GBC = "nintendo-game-boy-color-console"


def _fixture(kind):
    return json.loads((FIXTURE_DIR / f"{GBC}.{kind}.json").read_text())


def _token_route(mock):
    return mock.post(f"{HOST}/identity/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
    )


@respx.mock
def test_browse_search_parses_and_sends_expected_request():
    token = _token_route(respx)
    search = respx.get(f"{HOST}/buy/browse/v1/item_summary/search").mock(
        return_value=httpx.Response(200, json=_fixture("active"))
    )
    src = EbayApiSource("id", "secret")
    result = src.active("game boy color", "used", 50)

    assert token.called and search.call_count == 1
    req = search.calls[0].request
    assert req.headers["Authorization"] == "Bearer tok"
    assert req.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
    assert req.url.params["q"] == "game boy color"
    assert req.url.params["filter"] == "conditionIds:{3000},buyingOptions:{FIXED_PRICE}"
    assert req.url.params["limit"] == "50"
    token_body = token.calls[0].request.content.decode()
    assert "grant_type=client_credentials" in token_body

    assert result.total == _fixture("active")["total"]
    first = result.listings[0]
    assert first.status == "active" and first.item_id.startswith("v1|SAMPLE")
    assert any(item.price is None for item in result.listings)  # missing-price fixture row


@respx.mock
def test_token_is_cached_between_calls():
    token = _token_route(respx)
    respx.get(f"{HOST}/buy/browse/v1/item_summary/search").mock(
        return_value=httpx.Response(200, json={"total": 0, "itemSummaries": []})
    )
    src = EbayApiSource("id", "secret")
    src.active("a", "any", 10)
    src.active("b", "any", 10)
    assert token.call_count == 1


def test_sold_is_none_without_insights():
    assert EbayApiSource("id", "secret").sold("x", "any", 10) is None


@respx.mock
def test_insights_sold_parses_sales():
    _token_route(respx)
    respx.get(f"{HOST}/buy/marketplace_insights/v1_beta/item_sales/search").mock(
        return_value=httpx.Response(200, json=_fixture("sold"))
    )
    result = EbayApiSource("id", "secret", use_insights=True).sold("gbc", "any", 200)
    assert result.listings and all(i.status == "sold" for i in result.listings)
    assert all(i.sold_date is not None for i in result.listings)


@respx.mock
def test_insights_403_gives_clear_error():
    _token_route(respx)
    respx.get(f"{HOST}/buy/marketplace_insights/v1_beta/item_sales/search").mock(
        return_value=httpx.Response(403, json={"errors": [{"message": "Insufficient scope"}]})
    )
    with pytest.raises(ProviderError, match="Marketplace Insights"):
        EbayApiSource("id", "secret", use_insights=True).sold("gbc", "any", 10)


@respx.mock
def test_oauth_failure_raises():
    respx.post(f"{HOST}/identity/v1/oauth2/token").mock(
        return_value=httpx.Response(401, json={"error": "invalid_client"})
    )
    with pytest.raises(ProviderError, match="OAuth failed"):
        EbayApiSource("id", "secret").active("x", "any", 10)


@respx.mock
def test_sandbox_host():
    respx.post("https://api.sandbox.ebay.com/identity/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t", "expires_in": 7200})
    )
    route = respx.get("https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search").mock(
        return_value=httpx.Response(200, json={"total": 0})
    )
    EbayApiSource("id", "secret", environment="sandbox").active("x", "any", 500)
    assert route.calls[0].request.url.params["limit"] == "200"
