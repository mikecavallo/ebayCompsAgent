"""Official eBay APIs: Browse (active listings) and, optionally, Marketplace Insights (sold).

Browse API: available to any eBay developer app via OAuth client credentials.
Marketplace Insights API: returns sold items from the last 90 days, but eBay restricts it to
approved applications. It is off by default; enable with `use_insights=True` once approved.
"""

from __future__ import annotations

import base64
import time
from datetime import datetime
from typing import Any

import httpx

from ebay_comps.models import Condition, Listing, SearchResult
from ebay_comps.providers.base import ProviderError

HOSTS = {"production": "https://api.ebay.com", "sandbox": "https://api.sandbox.ebay.com"}
BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"
INSIGHTS_SCOPE = "https://api.ebay.com/oauth/api_scope/buy.marketplace.insights"
CONDITION_IDS = {"new": "1000", "used": "3000"}
BROWSE_MAX_LIMIT = 200


class EbayAuth:
    """Client-credentials token cache, one token per scope."""

    def __init__(self, client_id: str, client_secret: str, host: str, http: httpx.Client):
        self._basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._host = host
        self._http = http
        self._tokens: dict[str, tuple[str, float]] = {}

    def token(self, scope: str) -> str:
        cached = self._tokens.get(scope)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        resp = self._http.post(
            f"{self._host}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {self._basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": scope},
        )
        if resp.status_code != 200:
            raise ProviderError(
                f"eBay OAuth failed ({resp.status_code}) for scope {scope}: {resp.text[:200]}"
            )
        body = resp.json()
        self._tokens[scope] = (body["access_token"], time.time() + int(body["expires_in"]))
        return body["access_token"]


def _money(obj: dict[str, Any] | None) -> tuple[float | None, str | None]:
    if not obj or obj.get("value") in (None, ""):
        return None, None
    try:
        return float(obj["value"]), obj.get("currency")
    except (TypeError, ValueError):
        return None, None


def _shipping(summary: dict[str, Any]) -> float | None:
    costs = [_money(opt.get("shippingCost"))[0] for opt in summary.get("shippingOptions") or []]
    costs = [c for c in costs if c is not None]
    return min(costs) if costs else None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_browse_item(summary: dict[str, Any]) -> Listing:
    price, currency = _money(summary.get("price"))
    if price is None:  # auctions may only expose the current bid
        price, currency = _money(summary.get("currentBidPrice"))
    return Listing(
        item_id=summary["itemId"],
        title=summary.get("title", ""),
        status="active",
        price=price,
        currency=currency or "USD",
        shipping=_shipping(summary),
        condition=summary.get("condition"),
        condition_id=summary.get("conditionId"),
        buying_options=summary.get("buyingOptions") or [],
        url=summary.get("itemWebUrl"),
    )


def parse_sale_item(sale: dict[str, Any]) -> Listing:
    price, currency = _money(sale.get("lastSoldPrice"))
    return Listing(
        item_id=sale["itemId"],
        title=sale.get("title", ""),
        status="sold",
        price=price,
        currency=currency or "USD",
        shipping=_shipping(sale),
        condition=sale.get("condition"),
        condition_id=sale.get("conditionId"),
        buying_options=sale.get("buyingOptions") or [],
        url=sale.get("itemWebUrl"),
        sold_date=_parse_date(sale.get("lastSoldDate")),
        quantity_sold=sale.get("totalSoldQuantity"),
    )


def _filter(condition: Condition, buying_options: str | None = None) -> str | None:
    parts = []
    if condition in CONDITION_IDS:
        parts.append(f"conditionIds:{{{CONDITION_IDS[condition]}}}")
    if buying_options:
        parts.append(f"buyingOptions:{{{buying_options}}}")
    return ",".join(parts) or None


class EbayApiSource:
    """Listing source backed by eBay's official REST APIs."""

    sample_data = False

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        environment: str = "production",
        marketplace_id: str = "EBAY_US",
        use_insights: bool = False,
        http: httpx.Client | None = None,
    ):
        if environment not in HOSTS:
            raise ValueError(f"EBAY_ENV must be one of {sorted(HOSTS)}")
        self.host = HOSTS[environment]
        self.marketplace_id = marketplace_id
        self.use_insights = use_insights
        self._http = http or httpx.Client(timeout=20.0)
        self._auth = EbayAuth(client_id, client_secret, self.host, self._http)
        self.name = "ebay-browse" + ("+insights" if use_insights else "")

    def _get(self, path: str, scope: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = self._http.get(
            f"{self.host}{path}",
            params={k: v for k, v in params.items() if v is not None},
            headers={
                "Authorization": f"Bearer {self._auth.token(scope)}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
        )
        if resp.status_code == 403 and scope == INSIGHTS_SCOPE:
            raise ProviderError(
                "eBay denied Marketplace Insights access. This API is restricted; "
                "unset EBAY_USE_MARKETPLACE_INSIGHTS unless eBay has approved your app."
            )
        if resp.status_code != 200:
            raise ProviderError(f"eBay API error {resp.status_code} on {path}: {resp.text[:200]}")
        return resp.json()

    def active(self, query: str, condition: Condition, limit: int) -> SearchResult:
        body = self._get(
            "/buy/browse/v1/item_summary/search",
            BROWSE_SCOPE,
            {
                "q": query,
                "limit": min(limit, BROWSE_MAX_LIMIT),
                # Fixed-price only: auction current bids are not comparable asking prices.
                "filter": _filter(condition, "FIXED_PRICE"),
            },
        )
        items = [parse_browse_item(s) for s in body.get("itemSummaries") or []]
        return SearchResult(listings=items, total=body.get("total"))

    def sold(self, query: str, condition: Condition, limit: int) -> SearchResult | None:
        if not self.use_insights:
            return None
        body = self._get(
            "/buy/marketplace_insights/v1_beta/item_sales/search",
            INSIGHTS_SCOPE,
            {"q": query, "limit": min(limit, BROWSE_MAX_LIMIT), "filter": _filter(condition)},
        )
        items = [parse_sale_item(s) for s in body.get("itemSales") or []]
        return SearchResult(listings=items, total=body.get("total"))
