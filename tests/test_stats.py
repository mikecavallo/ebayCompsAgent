from ebay_comps.models import Listing
from ebay_comps.stats import clean_listings, compute_stats, sell_through, summarize


def L(i, price, title="Game Boy Color", status="active", shipping=None, currency="USD"):
    return Listing(item_id=str(i), title=title, status=status, price=price,
                   shipping=shipping, currency=currency)  # fmt: skip


def test_summarize_basic():
    s = summarize([10, 20, 30, 40, 50])
    assert s.count == 5 and s.median == 30 and s.min == 10 and s.max == 50
    assert s.p25 == 20 and s.p75 == 40 and s.iqr == 20


def test_summarize_empty_and_single():
    assert summarize([]) is None
    one = summarize([12.5])
    assert one.median == 12.5 and one.iqr == 0


def test_none_and_zero_prices_are_dropped_not_crashing():
    kept, removed = clean_listings([L(1, None), L(2, 0), L(3, 25)], "game boy")
    assert [k.item_id for k in kept] == ["3"]
    assert {r.reason for r in removed} == {"no price", "non-positive price"}


def test_keyword_filter_respects_query():
    items = [L(1, 20, "Game Boy Color FOR PARTS"), L(2, 60, "Game Boy Color")]
    kept, _ = clean_listings(items, "game boy color")
    assert [k.item_id for k in kept] == ["2"]
    kept, _ = clean_listings(items, "game boy color for parts")
    assert len(kept) == 2


def test_iqr_outliers_removed_per_status():
    items = [L(i, p) for i, p in enumerate([50, 52, 55, 57, 60, 500])]
    kept, removed = clean_listings(items, "q")
    assert 500 not in [k.price for k in kept]
    assert removed[0].reason.startswith("outlier: above")


def test_shipping_included_in_basis():
    kept, _ = clean_listings([L(1, 10, shipping=5)], "q")
    stats = compute_stats(kept, [], include_shipping=True)
    assert stats.active.median == 15
    stats = compute_stats(kept, [], include_shipping=False)
    assert stats.active.median == 10 and stats.price_basis == "item"


def test_minority_currency_dropped():
    items = [L(1, 10), L(2, 12), L(3, 11, currency="GBP")]
    kept, removed = clean_listings(items, "q")
    assert len(kept) == 2 and "currency" in removed[0].reason


def test_sell_through():
    assert sell_through(30, 70) == 0.3
    assert sell_through(None, 70) is None
    assert sell_through(0, 0) is None
