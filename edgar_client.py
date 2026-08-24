"""
edgar_client.py
----------------
Thin client for SEC EDGAR's free XBRL "company facts" API.

No API key required. SEC only asks that you set a descriptive User-Agent
(with an email) so they can contact you if your script misbehaves.

Docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""

import reques ts
import time

BASE_HEADERS = {
    # SEC requires a real identifying User-Agent. Replace the email below
    # with your own before running this for real.
    "User-Agent": "10K Insight Engine (your_email@example.com)"
}

TICKER_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def get_cik_for_ticker(ticker: str) -> str:
    """
    Look up a company's 10-digit zero-padded CIK from its stock ticker.
    SEC publishes a single JSON file mapping tickers -> CIKs.
    """
    resp = requests.get(TICKER_LOOKUP_URL, headers=BASE_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    ticker = ticker.upper()
    for entry in data.values():
        if entry["ticker"].upper() == ticker:
            return str(entry["cik_str"]).zfill(10)

    raise ValueError(f"Ticker '{ticker}' not found in SEC's ticker file.")


def get_company_facts(cik: str) -> dict:
    """
    Pull the full XBRL 'company facts' payload for a given CIK.
    This contains every financial concept (Revenue, Assets, Liabilities,
    etc.) the company has ever reported, tagged by fiscal period.
    """
    url = COMPANY_FACTS_URL.format(cik=cik)
    resp = requests.get(url, headers=BASE_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(0.2)  # be polite to SEC's rate limits
    return resp.json()


def extract_annual_series(facts_json: dict, us_gaap_tag: str) -> dict:
    """
    Extract a clean {fiscal_year: value} series for one US-GAAP concept
    (e.g. 'Assets', 'Liabilities', 'Revenues', 'NetIncomeLoss') from the
    raw company-facts payload, keeping only annual (10-K, full-year) data.
    """
    try:
        units = facts_json["facts"]["us-gaap"][us_gaap_tag]["units"]["USD"]
    except KeyError:
        return {}

    series = {}
    for item in units:
        # Annual figures: 'fp' == 'FY' and form is a 10-K
        if item.get("fp") == "FY" and item.get("form") == "10-K":
            fy = item.get("fy")
            if fy is not None:
                # Keep the most recently filed value if duplicates exist
                series[fy] = item["val"]

    return dict(sorted(series.items()))


if __name__ == "__main__":
    # Quick manual test
    cik = get_cik_for_ticker("AAPL")
    print(f"AAPL CIK: {cik}")
    facts = get_company_facts(cik)
    revenue = extract_annual_series(facts, "Revenues")
    print("Revenue by fiscal year:", revenue)
