"""The comps pipeline: fetch -> clean -> stats -> LLM recommendation."""

from __future__ import annotations

from datetime import datetime, timezone

from ebay_comps.llm.base import Advisor
from ebay_comps.models import CompsReport, Condition, Listing
from ebay_comps.providers.base import ListingSource
from ebay_comps.stats import clean_listings, compute_stats


def run_comps(
    query: str,
    source: ListingSource,
    advisor: Advisor,
    *,
    condition: Condition = "any",
    limit: int = 100,
    include_shipping: bool = True,
) -> CompsReport:
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")

    active = source.active(query, condition, limit)
    sold = source.sold(query, condition, limit)

    raw: list[Listing] = list(active.listings) + (list(sold.listings) if sold else [])
    kept, removed = clean_listings(raw, query, include_shipping=include_shipping)
    stats = compute_stats(
        kept,
        removed,
        include_shipping=include_shipping,
        active_total=active.total,
        sold_total=sold.total if sold else None,
    )
    # Sold comps first: they are the stronger evidence for the advisor.
    comps = sorted(kept, key=lambda c: (c.status != "sold", c.total_price or 0))
    recommendation = advisor.recommend(query, condition, stats, comps)
    return CompsReport(
        query=query,
        condition=condition,
        source=source.name,
        llm=advisor.name,
        sample_data=source.sample_data,
        generated_at=datetime.now(timezone.utc),
        stats=stats,
        comps=comps,
        recommendation=recommendation,
    )
