from __future__ import annotations

import json
from typing import Protocol

from ebay_comps.models import CompsStats, Condition, Listing, PricingRecommendation

MAX_COMPS_IN_PROMPT = 40


class AdvisorError(RuntimeError):
    """Raised when an LLM provider cannot produce a recommendation."""


class Advisor(Protocol):
    name: str

    def recommend(
        self, query: str, condition: Condition, stats: CompsStats, comps: list[Listing]
    ) -> PricingRecommendation: ...


SYSTEM_PROMPT = """\
You are a pricing analyst for an eBay reseller. You receive cleaned comparable listings and
summary statistics for one item, and you return a pricing recommendation.

Rules:
- Base every number on the data provided. Do not invent sales, prices, or market facts.
- Sold prices are evidence of what buyers paid. Active prices are asking prices from
  competing sellers and usually run higher than what actually sells. If there is no sold
  data, say so in the caveats and treat active prices as a ceiling, not a market value.
- Prices are in the stated currency and on the stated basis (item price, or item plus
  shipping). Keep your recommendation on the same basis.
- If the comps look like a different product, bundle, or condition than the query, call that
  out in the caveats and lower your confidence.
- Confidence: "high" needs plenty of sold comps with a tight IQR; "low" for thin or
  active-only data.
- quick_sale_price <= recommended_price, and price_range_low <= price_range_high.
- Keep reasoning to 2-5 sentences that cite the statistics you used."""


def build_user_prompt(
    query: str, condition: Condition, stats: CompsStats, comps: list[Listing]
) -> str:
    sample = [
        {
            "status": c.status,
            "title": c.title,
            "price": c.price,
            "shipping": c.shipping,
            "condition": c.condition,
            "sold_date": c.sold_date.date().isoformat() if c.sold_date else None,
        }
        for c in comps[:MAX_COMPS_IN_PROMPT]
    ]
    stats_json = stats.model_dump(exclude={"removed"})
    stats_json["removed_count"] = len(stats.removed)
    return (
        f"Item to price: {query}\n"
        f"Condition filter: {condition}\n\n"
        f"Summary statistics:\n{json.dumps(stats_json, indent=2)}\n\n"
        f"Comparable listings (up to {MAX_COMPS_IN_PROMPT}):\n{json.dumps(sample, indent=2)}"
    )
