"""Plain-text rendering of a CompsReport for the terminal."""

from __future__ import annotations

import textwrap

from ebay_comps.models import CompsReport, PriceStats


def _stats_line(label: str, s: PriceStats | None, total: int | None) -> str:
    if s is None:
        return f"  {label:<7} no data"
    seen = f" of {total}" if total is not None else ""
    return (
        f"  {label:<7} n={s.count}{seen:<9} median {s.median:>8.2f}   "
        f"IQR {s.p25:.2f}-{s.p75:.2f}   range {s.min:.2f}-{s.max:.2f}"
    )


def render_text(report: CompsReport, show_comps: int = 8) -> str:
    st, rec = report.stats, report.recommendation
    out = []
    if report.sample_data:
        out.append("*** SAMPLE DATA: bundled synthetic fixtures, not live eBay listings ***")
    out.append(f"Comps for: {report.query}  (condition: {report.condition})")
    out.append(f"Source: {report.source}   Advisor: {report.llm}")
    out.append(f"Prices in {st.currency}, basis: {st.price_basis}")
    out.append("")
    out.append("Statistics (after cleaning)")
    out.append(_stats_line("Sold", st.sold, st.sold_total))
    out.append(_stats_line("Active", st.active, st.active_total))
    if st.sell_through is not None:
        out.append(f"  Sell-through: {st.sell_through:.0%} (sold / (sold + active))")
    else:
        out.append("  Sell-through: n/a (needs sold data)")
    if st.removed:
        reasons: dict[str, int] = {}
        for r in st.removed:
            key = r.reason.split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
        summary = ", ".join(f"{n} {k}" for k, n in sorted(reasons.items()))
        out.append(f"  Removed {len(st.removed)} listings: {summary}")
    out.append("")
    out.append("Recommendation")
    out.append(f"  List at:     {rec.recommended_price:.2f}")
    out.append(f"  Quick sale:  {rec.quick_sale_price:.2f}")
    out.append(f"  Range:       {rec.price_range_low:.2f} - {rec.price_range_high:.2f}")
    out.append(f"  Confidence:  {rec.confidence}")
    out.append(textwrap.fill(rec.reasoning, 88, initial_indent="  ", subsequent_indent="  "))
    for c in rec.caveats:
        out.append(textwrap.fill(c, 88, initial_indent="  - ", subsequent_indent="    "))
    if show_comps and report.comps:
        out.append("")
        out.append(f"Top comps (of {len(report.comps)} kept)")
        for c in report.comps[:show_comps]:
            when = f" {c.sold_date:%Y-%m-%d}" if c.sold_date else ""
            out.append(f"  {c.status:<6}{when:<11} {c.total_price:>8.2f}  {c.title[:58]}")
    return "\n".join(out)
