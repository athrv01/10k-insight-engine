"""
nse_bse_client.py
------------------
Data client for Indian stock exchanges (NSE and BSE).

SEC EDGAR only covers US-listed companies, so Indian tickers need a
different data source entirely. This uses yfinance (free, no API key),
which can pull financial statements for NSE (.NS suffix) and BSE (.BO
suffix) tickers.

IMPORTANT CAVEAT: Yahoo Finance's row-naming schema for financial
statements has drifted across versions and isn't as standardized as
SEC's XBRL tags. The TAG_MAP below lists the most common row names seen
in practice, with fallbacks, but if a ratio comes back as None/missing
for an NSE/BSE ticker, run debug_nse_bse.py first — it prints every raw
row name yfinance actually returned, so you can add the correct name to
the map below rather than guessing.
"""

import yfinance as yf
import pandas as pd

# Maps our canonical tag names (same ones ratios.py expects) to the
# possible row names yfinance might use. First match wins.
BALANCE_SHEET_TAG_MAP = {
    "Assets": ["Total Assets"],
    "AssetsCurrent": ["Current Assets"],
    "LiabilitiesCurrent": ["Current Liabilities"],
    "Liabilities": ["Total Liabilities Net Minority Interest", "Total Liab"],
    "StockholdersEquity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "InventoryNet": ["Inventory"],
    "CashAndCashEquivalentsAtCarryingValue": [
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
    ],
}

INCOME_STATEMENT_TAG_MAP = {
    "Revenues": ["Total Revenue", "Operating Revenue"],
    "CostOfGoodsAndServicesSold": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
    "NetIncomeLoss": ["Net Income", "Net Income Common Stockholders"],
    "GrossProfit": ["Gross Profit"],
    "OperatingIncomeLoss": ["Operating Income"],
    "InterestExpense": ["Interest Expense", "Interest Expense Non Operating"],
}


def normalize_ticker(ticker: str, exchange: str) -> str:
    """Append the correct Yahoo Finance suffix for the chosen exchange."""
    ticker = ticker.upper().strip()
    if exchange == "NSE" and not ticker.endswith(".NS"):
        ticker += ".NS"
    elif exchange == "BSE" and not ticker.endswith(".BO"):
        ticker += ".BO"
    return ticker


def _extract_series(df: pd.DataFrame, candidate_names: list) -> dict:
    """
    Given a yfinance annual statement DataFrame (rows = line items,
    columns = fiscal year-end timestamps), find the first matching row
    name from candidate_names and return it as {fiscal_year: value}.
    """
    if df is None or df.empty:
        return {}

    for name in candidate_names:
        if name in df.index:
            row = df.loc[name]
            series = {}
            for col, val in row.items():
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    continue
                fy = col.year if hasattr(col, "year") else int(str(col)[:4])
                series[fy] = float(val)
            return series

    return {}


def get_company_facts(ticker: str, exchange: str):
    """
    Fetch annual financials for an NSE/BSE ticker and return them already
    mapped into the same canonical {tag: {fiscal_year: value}} shape that
    ratios.compute_ratios() expects — so the rest of the pipeline (ratios,
    anomaly flags, rule-based narrative) works identically regardless of
    whether the data came from SEC EDGAR or here.

    Returns (company_name, data_dict).
    """
    full_ticker = normalize_ticker(ticker, exchange)
    t = yf.Ticker(full_ticker)

    balance_sheet = t.balance_sheet
    financials = t.financials
    info = t.info or {}
    company_name = info.get("longName") or info.get("shortName") or full_ticker

    data = {}
    for tag, candidates in BALANCE_SHEET_TAG_MAP.items():
        data[tag] = _extract_series(balance_sheet, candidates)
    for tag, candidates in INCOME_STATEMENT_TAG_MAP.items():
        data[tag] = _extract_series(financials, candidates)

    return company_name, data


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python nse_bse_client.py TICKER NSE|BSE")
        sys.exit(1)
    name, data = get_company_facts(sys.argv[1], sys.argv[2].upper())
    print(f"Company: {name}")
    for tag, series in data.items():
        print(f"{tag}: {series}")
