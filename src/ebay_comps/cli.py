"""Command-line interface: `ebay-comps "item description"`."""

from __future__ import annotations

import argparse
import sys

from ebay_comps.agent import run_comps
from ebay_comps.config import LLMS, SOURCES, ConfigError, make_advisor, make_source
from ebay_comps.export import push_airtable, write_csv
from ebay_comps.llm.base import AdvisorError
from ebay_comps.providers.base import ProviderError
from ebay_comps.render import render_text


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ebay-comps",
        description="Price an item from comparable eBay listings.",
    )
    p.add_argument("query", help='Item description, e.g. "Nintendo Game Boy Color console"')
    p.add_argument("--condition", choices=["any", "new", "used"], default="any")
    p.add_argument("--limit", type=int, default=100, help="Max listings per search (<=200)")
    p.add_argument(
        "--source",
        choices=SOURCES,
        default="auto",
        help="auto = eBay API if EBAY_* keys are set, else bundled sample fixtures",
    )
    p.add_argument(
        "--llm",
        choices=LLMS,
        default="auto",
        help="auto = anthropic, then openai, then mock, by which API key is set",
    )
    p.add_argument("--demo", action="store_true", help="Offline demo: --source fixture --llm mock")
    p.add_argument(
        "--item-price-only", action="store_true", help="Ignore shipping when computing statistics"
    )
    p.add_argument("--json", action="store_true", help="Print the full report as JSON")
    p.add_argument("--csv", metavar="PATH", help="Write kept comps to a CSV file")
    p.add_argument(
        "--airtable",
        action="store_true",
        help="Upsert kept comps to Airtable (AIRTABLE_* env vars)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.demo:
        args.source, args.llm = "fixture", "mock"
    try:
        report = run_comps(
            args.query,
            make_source(args.source),
            make_advisor(args.llm),
            condition=args.condition,
            limit=args.limit,
            include_shipping=not args.item_price_only,
        )
    except (ConfigError, ProviderError, AdvisorError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(report.model_dump_json(indent=2) if args.json else render_text(report))
    try:
        if args.csv:
            n = write_csv(report, args.csv)
            print(f"\nWrote {n} comps to {args.csv}", file=sys.stderr)
        if args.airtable:
            n = push_airtable(report)
            print(f"\nUpserted {n} comps to Airtable", file=sys.stderr)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
