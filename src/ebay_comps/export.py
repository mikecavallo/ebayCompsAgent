"""Export comps to CSV or Airtable."""

from __future__ import annotations

import csv
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ebay_comps.models import CompsReport

CSV_FIELDS = [
    "query", "item_id", "status", "title", "price", "shipping", "total_price",
    "currency", "condition", "sold_date", "url",
]  # fmt: skip


def _rows(report: CompsReport) -> list[dict[str, Any]]:
    return [
        {
            "query": report.query,
            "item_id": c.item_id,
            "status": c.status,
            "title": c.title,
            "price": c.price,
            "shipping": c.shipping,
            "total_price": c.total_price,
            "currency": c.currency,
            "condition": c.condition,
            "sold_date": c.sold_date.date().isoformat() if c.sold_date else "",
            "url": c.url or "",
        }
        for c in report.comps
    ]


def write_csv(report: CompsReport, path: str | Path) -> int:
    rows = _rows(report)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


AIRTABLE_FIELD_NAMES = {
    "query": "Query",
    "item_id": "Item ID",
    "status": "Status",
    "title": "Title",
    "price": "Price",
    "shipping": "Shipping",
    "total_price": "Total Price",
    "currency": "Currency",
    "condition": "Condition",
    "sold_date": "Sold Date",
    "url": "URL",
}


def push_airtable(
    report: CompsReport, env: Mapping[str, str] | None = None, table: Any | None = None
) -> int:
    """Upsert comps into Airtable keyed on "Item ID" (re-runs update rather than duplicate).

    Configure with AIRTABLE_API_KEY, AIRTABLE_BASE_ID and AIRTABLE_TABLE_NAME (default "Comps").
    The table needs the columns named in AIRTABLE_FIELD_NAMES.
    """
    if table is None:
        env = os.environ if env is None else env
        missing = [k for k in ("AIRTABLE_API_KEY", "AIRTABLE_BASE_ID") if not env.get(k)]
        if missing:
            raise RuntimeError(f"Airtable export needs {', '.join(missing)}")
        try:
            from pyairtable import Api
        except ImportError as exc:
            raise RuntimeError('Airtable export needs: pip install "ebay-comps[airtable]"') from exc
        table = Api(env["AIRTABLE_API_KEY"]).table(
            env["AIRTABLE_BASE_ID"], env.get("AIRTABLE_TABLE_NAME") or "Comps"
        )
    records = [
        {"fields": {AIRTABLE_FIELD_NAMES[k]: v for k, v in row.items() if v not in (None, "")}}
        for row in _rows(report)
    ]
    if records:
        table.batch_upsert(records, key_fields=["Item ID"], typecast=True)
    return len(records)
