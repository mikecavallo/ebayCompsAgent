"""Offline listing source backed by JSON files shaped like eBay API responses.

The bundled fixtures are synthetic sample data (not real listings). They exist so the CLI,
web UI, and tests run without network access or credentials.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ebay_comps.models import Condition, SearchResult
from ebay_comps.providers.base import ProviderError
from ebay_comps.providers.ebay import CONDITION_IDS, parse_browse_item, parse_sale_item

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class FixtureSource:
    name = "fixture"
    sample_data = True

    def __init__(self, directory: Path = FIXTURE_DIR):
        self.directory = directory
        self.datasets = sorted(
            p.name[: -len(".active.json")] for p in directory.glob("*.active.json")
        )

    def _match(self, query: str) -> str:
        q = _tokens(query)
        scored = [(len(q & _tokens(name.replace("-", " "))), name) for name in self.datasets]
        best = max(scored, default=(0, ""))
        if best[0] == 0:
            raise ProviderError(
                f"No sample fixture matches {query!r}. Sample datasets: "
                f"{', '.join(self.datasets)}. Set EBAY_CLIENT_ID/EBAY_CLIENT_SECRET for live data."
            )
        return best[1]

    def _load(self, dataset: str, kind: str) -> dict | None:
        path = self.directory / f"{dataset}.{kind}.json"
        return json.loads(path.read_text()) if path.exists() else None

    @staticmethod
    def _condition_ok(condition_id: str | None, condition: Condition) -> bool:
        return condition == "any" or condition_id == CONDITION_IDS[condition]

    def active(self, query: str, condition: Condition, limit: int) -> SearchResult:
        body = self._load(self._match(query), "active") or {}
        items = [parse_browse_item(s) for s in body.get("itemSummaries", [])]
        items = [i for i in items if self._condition_ok(i.condition_id, condition)]
        return SearchResult(listings=items[:limit], total=len(items))

    def sold(self, query: str, condition: Condition, limit: int) -> SearchResult | None:
        body = self._load(self._match(query), "sold")
        if body is None:
            return None
        items = [parse_sale_item(s) for s in body.get("itemSales", [])]
        items = [i for i in items if self._condition_ok(i.condition_id, condition)]
        return SearchResult(listings=items[:limit], total=len(items))
