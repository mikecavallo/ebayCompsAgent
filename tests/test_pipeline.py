import json

import pytest

from ebay_comps.agent import run_comps
from ebay_comps.cli import main
from ebay_comps.config import ConfigError, make_advisor, make_source
from ebay_comps.export import push_airtable, write_csv
from ebay_comps.llm import AnthropicAdvisor, MockAdvisor
from ebay_comps.models import CompsStats, Listing
from ebay_comps.providers import EbayApiSource, FixtureSource
from ebay_comps.providers.base import ProviderError

from .conftest import GBC


def test_demo_pipeline_end_to_end(fixture_source, mock_advisor):
    r = run_comps(GBC, fixture_source, mock_advisor)
    assert r.sample_data is True and r.source == "fixture"
    assert r.stats.sold and r.stats.active and r.stats.sell_through is not None
    # junk listings (parts, lots, box only, missing price) and outliers are removed
    reasons = " ".join(x.reason for x in r.stats.removed)
    for word in ("for parts", "lot of", "box only", "no price", "outlier"):
        assert word in reasons
    rec = r.recommendation
    assert rec.quick_sale_price <= rec.recommended_price
    assert rec.price_range_low <= rec.price_range_high
    assert r.comps[0].status == "sold"


def test_condition_filter(fixture_source, mock_advisor):
    r = run_comps(GBC, fixture_source, mock_advisor, condition="new")
    assert all(c.condition_id == "1000" for c in r.comps)


def test_unknown_fixture_query_is_explicit(fixture_source, mock_advisor):
    with pytest.raises(ProviderError, match="No sample fixture"):
        run_comps("iphone 15 pro", fixture_source, mock_advisor)


def test_empty_query_rejected(fixture_source, mock_advisor):
    with pytest.raises(ValueError):
        run_comps("  ", fixture_source, mock_advisor)


def test_mock_advisor_active_only_is_low_confidence():
    stats = CompsStats(currency="USD", price_basis="item")
    from ebay_comps.stats import summarize

    stats.active = summarize([50, 60, 70, 80])
    rec = MockAdvisor().recommend("x", "any", stats, [])
    assert rec.confidence == "low" and any("No sold data" in c for c in rec.caveats)


def test_config_auto_resolution(monkeypatch):
    assert isinstance(make_source("auto", {}), FixtureSource)
    src = make_source("auto", {"EBAY_CLIENT_ID": "a", "EBAY_CLIENT_SECRET": "b"})
    assert isinstance(src, EbayApiSource) and src.use_insights is False
    src = make_source("ebay", {"EBAY_CLIENT_ID": "a", "EBAY_CLIENT_SECRET": "b",
                               "EBAY_USE_MARKETPLACE_INSIGHTS": "1"})  # fmt: skip
    assert src.use_insights is True
    assert isinstance(make_advisor("auto", {}), MockAdvisor)
    adv = make_advisor("auto", {"ANTHROPIC_API_KEY": "sk-test", "OPENAI_API_KEY": "x"})
    assert isinstance(adv, AnthropicAdvisor) and adv.model == "claude-sonnet-5-5"
    with pytest.raises(ConfigError):
        make_source("ebay", {})
    with pytest.raises(ConfigError):
        make_advisor("anthropic", {})


def test_cli_demo_text(capsys):
    assert main(["--demo", GBC]) == 0
    out = capsys.readouterr().out
    assert "SAMPLE DATA" in out and "List at:" in out


def test_cli_json_and_csv(tmp_path, capsys):
    path = tmp_path / "comps.csv"
    assert main(["--demo", GBC, "--json", "--csv", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sample_data"] is True
    lines = path.read_text().splitlines()
    assert lines[0].startswith("query,item_id,status") and len(lines) == len(report["comps"]) + 1


def test_cli_error_exit_code(capsys):
    assert main(["--demo", "iphone"]) == 2
    assert "No sample fixture" in capsys.readouterr().err


def test_csv_export(tmp_path, fixture_source, mock_advisor):
    r = run_comps(GBC, fixture_source, mock_advisor)
    assert write_csv(r, tmp_path / "x.csv") == len(r.comps)


def test_airtable_upsert_keyed_on_item_id(fixture_source, mock_advisor):
    class FakeTable:
        def __init__(self):
            self.calls = []

        def batch_upsert(self, records, key_fields, typecast):
            self.calls.append((records, key_fields, typecast))

    r = run_comps(GBC, fixture_source, mock_advisor)
    table = FakeTable()
    assert push_airtable(r, table=table) == len(r.comps)
    records, key_fields, _ = table.calls[0]
    assert key_fields == ["Item ID"]
    assert records[0]["fields"]["Item ID"] and "Total Price" in records[0]["fields"]


def test_airtable_requires_env(fixture_source, mock_advisor):
    r = run_comps(GBC, fixture_source, mock_advisor)
    with pytest.raises(RuntimeError, match="AIRTABLE_BASE_ID"):
        push_airtable(r, env={"AIRTABLE_API_KEY": "x"})


def test_listing_total_price():
    item = Listing(item_id="1", title="t", status="active", price=10.0, shipping=4.99)
    assert item.total_price == 14.99
