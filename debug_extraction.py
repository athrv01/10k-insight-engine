"""
debug_extraction.py
--------------------
Diagnostic tool: prints every raw US-GAAP line item, per fiscal year,
exactly as extracted from SEC EDGAR — before any ratio math happens.

Use this when a ratio looks implausible. A ratio like "ROE jumped 673%"
almost always traces back to ONE underlying line item (Assets, Equity,
NetIncomeLoss, etc.) having a wrong value for a specific year — this
script lets you see the raw numbers and spot which one is off, by
comparing against a source you trust (e.g. macrotrends.net or the
actual 10-K filing).

Usage:
    python debug_extraction.py AAPL
"""

import sys
from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series
from ratios import REQUIRED_TAGS


def main(ticker):
    print(f"Looking up CIK for {ticker}...")
    cik = get_cik_for_ticker(ticker)
    print(f"Pulling company facts for CIK {cik}...\n")
    facts = get_company_facts(cik)

    all_years = set()
    data = {}
    for tag in REQUIRED_TAGS:
        series = extract_annual_series(facts, tag)
        data[tag] = series
        all_years.update(series.keys())

    years = sorted(all_years)

    # Print a simple table: tag down the side, years across the top
    col_width = 18
    header = "TAG".ljust(40) + "".join(str(y).rjust(col_width) for y in years)
    print(header)
    print("-" * len(header))

    for tag in REQUIRED_TAGS:
        row = tag.ljust(40)
        for y in years:
            val = data[tag].get(y)
            if val is None:
                cell = "—"
            else:
                # Format big dollar figures compactly (billions)
                cell = f"{val/1e9:,.2f}B" if abs(val) >= 1e9 else f"{val:,.0f}"
            row += cell.rjust(col_width)
        print(row)

    print("\nCross-check any suspicious column against a source you trust")
    print("(e.g. macrotrends.net, stockanalysis.com, or the actual 10-K).")
    print("A ratio that spikes/craters in one specific year almost always")
    print("traces back to exactly one wrong number in this table.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python debug_extraction.py TICKER")
        sys.exit(1)
    main(sys.argv[1])
