"""Cleaning and outlier-robust statistics for comparable listings."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable

from ebay_comps.models import CompsStats, Listing, PriceStats, RemovedListing

# Title phrases that usually mean "not the same thing as a working, single unit".
# A phrase is only applied when it does not also appear in the user's query, so a
# search for "game boy for parts" still keeps parts listings.
DEFAULT_EXCLUDE_PHRASES: tuple[str, ...] = (
    "for parts",
    "not working",
    "parts only",
    "as-is",
    "as is",
    "broken",
    "box only",
    "empty box",
    "manual only",
    "lot of",
    "bundle of",
    "replacement shell",
)


def _price(listing: Listing, include_shipping: bool) -> float | None:
    return listing.total_price if include_shipping else listing.price


def clean_listings(
    listings: Iterable[Listing],
    query: str,
    *,
    include_shipping: bool = True,
    exclude_phrases: Iterable[str] = DEFAULT_EXCLUDE_PHRASES,
    iqr_k: float = 1.5,
) -> tuple[list[Listing], list[RemovedListing]]:
    """Drop unusable listings, keyword mismatches, and Tukey-fence outliers.

    Returns (kept, removed). Outlier fences are computed per status (active vs sold)
    because asking prices and sale prices have different distributions.
    """
    q = query.lower()
    phrases = [p for p in exclude_phrases if p not in q]
    listings = list(listings)

    kept: list[Listing] = []
    removed: list[RemovedListing] = []

    def drop(item: Listing, reason: str) -> None:
        removed.append(RemovedListing(item_id=item.item_id, title=item.title, reason=reason))

    currencies = Counter(item.currency for item in listings if item.price is not None)
    main_currency = currencies.most_common(1)[0][0] if currencies else "USD"

    for item in listings:
        price = _price(item, include_shipping)
        title = item.title.lower()
        hit = next((p for p in phrases if p in title), None)
        if price is None:
            drop(item, "no price")
        elif price <= 0:
            drop(item, "non-positive price")
        elif item.currency != main_currency:
            drop(item, f"currency {item.currency} != {main_currency}")
        elif hit:
            drop(item, f"title contains '{hit}'")
        else:
            kept.append(item)

    final: list[Listing] = []
    for status in ("active", "sold"):
        group = [item for item in kept if item.status == status]
        prices = [_price(item, include_shipping) for item in group]
        if len(group) < 4:
            final.extend(group)
            continue
        q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
        spread = q3 - q1
        low, high = q1 - iqr_k * spread, q3 + iqr_k * spread
        for item, price in zip(group, prices, strict=True):
            if price < low:
                drop(item, f"outlier: below {low:.2f}")
            elif price > high:
                drop(item, f"outlier: above {high:.2f}")
            else:
                final.append(item)
    return final, removed


def summarize(prices: list[float]) -> PriceStats | None:
    if not prices:
        return None
    if len(prices) == 1:
        p = prices[0]
        return PriceStats(count=1, median=p, mean=p, p25=p, p75=p, iqr=0.0, min=p, max=p)
    q1, med, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    return PriceStats(
        count=len(prices),
        median=round(med, 2),
        mean=round(statistics.fmean(prices), 2),
        p25=round(q1, 2),
        p75=round(q3, 2),
        iqr=round(q3 - q1, 2),
        min=round(min(prices), 2),
        max=round(max(prices), 2),
    )


def sell_through(sold_total: int | None, active_total: int | None) -> float | None:
    """Share of supply that sold: sold / (sold + active). None if either count is unknown."""
    if sold_total is None or active_total is None or sold_total + active_total == 0:
        return None
    return round(sold_total / (sold_total + active_total), 3)


def compute_stats(
    kept: list[Listing],
    removed: list[RemovedListing],
    *,
    include_shipping: bool = True,
    active_total: int | None = None,
    sold_total: int | None = None,
) -> CompsStats:
    def prices(status: str) -> list[float]:
        return [_price(i, include_shipping) for i in kept if i.status == status]

    currency = Counter(i.currency for i in kept).most_common(1)[0][0] if kept else "USD"
    return CompsStats(
        currency=currency,
        price_basis="item+shipping" if include_shipping else "item",
        active=summarize(prices("active")),
        sold=summarize(prices("sold")),
        active_total=active_total,
        sold_total=sold_total,
        sell_through=sell_through(sold_total, active_total),
        removed=removed,
    )
