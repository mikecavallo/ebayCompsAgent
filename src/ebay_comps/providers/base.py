from __future__ import annotations

from typing import Protocol

from ebay_comps.models import Condition, SearchResult


class ProviderError(RuntimeError):
    """Raised when a listing source cannot satisfy a request."""


class ListingSource(Protocol):
    name: str
    sample_data: bool

    def active(self, query: str, condition: Condition, limit: int) -> SearchResult: ...

    def sold(self, query: str, condition: Condition, limit: int) -> SearchResult | None:
        """Recently sold listings, or None when this source has no sold data."""
        ...
