"""
debug_nse_bse.py
-----------------
Diagnostic tool for the NSE/BSE (yfinance) data path.

Yahoo Finance's row-naming schema for financial statements isn't as
standardized as SEC's XBRL tags, and it has drifted across yfinance
versions. If a ratio comes back as None/missing for an Indian ticker,
run this FIRST — it prints:

  1. Every raw row name yfinance actually returned (so you can see if
     our TAG_MAP in nse_bse_client.py is missing the right name)
  2. What we successfully mapped to our canonical tags

Usage:
    python debug_nse_bse.py RELIANCE NSE
    python debug_nse_bse.py TCS NSE
    python debug_nse_bse.py 500325 BSE
"""

import sys
import yfinance as yf
from nse_bse_client import normalize_ticker, get_company_facts, BALANCE_SHEET_TAG_MAP, INCOME_STATEMENT_TAG_MAP


def main(ticker, exchange):
    full_ticker = normalize_ticker(ticker, exchange)
    print(f"Fetching {full_ticker} from Yahoo Finance...\n")

    t = yf.Ticker(full_ticker)
    balance_sheet = t.balance_sheet
    financials = t.financials

    print("=" * 70)
    print("RAW BALANCE SHEET ROW NAMES (yfinance actually returned these):")
    print("=" * 70)
    if balance_sheet is not None and not balance_sheet.empty:
        for row_name in balance_sheet.index:
            print(f"  {row_name}")
    else:
        print("  (empty — yfinance returned no balance sheet data for this ticker)")

    print("\n" + "=" * 70)
    print("RAW INCOME STATEMENT ROW NAMES:")
    print("=" * 70)
    if financials is not None and not financials.empty:
        for row_name in financials.index:
            print(f"  {row_name}")
    else:
        print("  (empty — yfinance returned no income statement data for this ticker)")

    print("\n" + "=" * 70)
    print("WHAT WE SUCCESSFULLY MAPPED TO CANONICAL TAGS:")
    print("=" * 70)
    company_name, data = get_company_facts(ticker, exchange)
    print(f"Company: {company_name}\n")
    for tag, series in data.items():
        status = "OK" if series else "MISSING — check the raw row names above and add to nse_bse_client.py's TAG_MAP"
        print(f"  {tag:45s}: {series if series else '{}'}  [{status}]")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python debug_nse_bse.py TICKER NSE|BSE")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2].upper())
