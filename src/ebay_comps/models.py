"""Data models shared across providers, statistics, and the LLM layer."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Condition = Literal["any", "new", "used"]
ListingStatus = Literal["active", "sold"]


class Listing(BaseModel):
    """One comparable listing, normalized from whichever provider produced it."""

    item_id: str
    title: str
    status: ListingStatus
    price: float | None
    currency: str = "USD"
    shipping: float | None = None
    condition: str | None = None
    condition_id: str | None = None
    buying_options: list[str] = Field(default_factory=list)
    url: str | None = None
    sold_date: datetime | None = None
    quantity_sold: int | None = None

    @property
    def total_price(self) -> float | None:
        """Item price plus shipping when shipping is known (the buyer's landed cost)."""
        if self.price is None:
            return None
        return round(self.price + (self.shipping or 0.0), 2)


class SearchResult(BaseModel):
    listings: list[Listing]
    total: int | None = None
    """Total matches reported by the source (can exceed len(listings))."""


class RemovedListing(BaseModel):
    item_id: str
    title: str
    reason: str


class PriceStats(BaseModel):
    count: int
    median: float
    mean: float
    p25: float
    p75: float
    iqr: float
    min: float
    max: float


class CompsStats(BaseModel):
    currency: str
    price_basis: Literal["item+shipping", "item"]
    active: PriceStats | None = None
    sold: PriceStats | None = None
    active_total: int | None = None
    sold_total: int | None = None
    sell_through: float | None = None
    """sold / (sold + active) when both counts are available, else None."""
    removed: list[RemovedListing] = Field(default_factory=list)


class PricingRecommendation(BaseModel):
    """Structured output the LLM must return."""

    recommended_price: float = Field(description="Suggested Buy It Now list price.")
    quick_sale_price: float = Field(description="Price likely to sell quickly.")
    price_range_low: float
    price_range_high: float
    confidence: Literal["low", "medium", "high"]
    reasoning: str = Field(description="2-5 sentences citing the statistics provided.")
    caveats: list[str] = Field(default_factory=list)


class CompsReport(BaseModel):
    query: str
    condition: Condition
    source: str
    llm: str
    sample_data: bool
    generated_at: datetime
    stats: CompsStats
    comps: list[Listing]
    recommendation: PricingRecommendation
