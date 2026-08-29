"""
edgar_client.py
----------------
Thin client for SEC EDGAR's free XBRL "company facts" API.

No API key required. SEC only asks that you set a descriptive User-Agent
(with an email) so they can contact you if your script misbehaves.

Docs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
"""

import requests
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

    IMPORTANT — why we don't group by SEC's own 'fy' field:
    SEC's provided 'fy' label is not reliably tied to the period a fact
    actually covers. When a prior year's figure is re-disclosed as a
    comparative inside a LATER 10-K, SEC sometimes tags it with a 'fy'
    that doesn't match its real 'end' date — and different concepts can
    be mislabeled by different amounts (empirically, duration items like
    Revenue were seen shifted +2 years, while instant items like Assets
    were shifted +1 year, in the same company's data). Grouping by the
    provided 'fy' silently mixes values from different real fiscal years
    into ratios, producing implausible swings (e.g. a ratio "jumping"
    600%+ in one year because its numerator and denominator quietly came
    from different years).

    The fix: derive the fiscal year directly from each fact's own 'end'
    date instead of trusting SEC's label. The end date is unambiguous and
    can't be mislabeled, and for the vast majority of US filers (any
    fiscal year-end month) the calendar year of the period-end date
    matches how that fiscal year is actually named.

    Two additional correctness checks:
    1. Stub/partial periods: duration-type concepts should span ~12
       months. A fiscal year-end change can produce a shorter period
       that's technically tagged 'FY' but would distort ratios if
       treated as a full year — we reject anything not roughly annual.
    2. Duplicates for the same real fiscal year (e.g. a value re-stated
       in a later filing): we keep the EARLIEST-filed entry, i.e. the
       figure as originally reported in that year's own 10-K.
    """
    try:
        units = facts_json["facts"]["us-gaap"][us_gaap_tag]["units"]["USD"]
    except KeyError:
        return {}

    from datetime import date

    candidates = {}  # real_fy (derived from end date) -> list of (filed_date, val)
    for item in units:
        if item.get("fp") != "FY" or item.get("form") != "10-K":
            continue

        end = item.get("end")
        if not end:
            continue
        try:
            end_date = date.fromisoformat(end)
        except ValueError:
            continue

        start = item.get("start")
        if start:
            try:
                span_days = (end_date - date.fromisoformat(start)).days
            except ValueError:
                span_days = None
            if span_days is not None and not (350 <= span_days <= 380):
                continue  # stub/partial period — skip it

        real_fy = end_date.year
        filed = item.get("filed", "")
        candidates.setdefault(real_fy, []).append((filed, item["val"]))

    series = {}
    for fy, entries in candidates.items():
        # Earliest-filed entry = the value as originally reported in that
        # fiscal year's own 10-K, not a later comparative restatement.
        entries.sort(key=lambda pair: pair[0])
        series[fy] = entries[0][1]

    return dict(sorted(series.items()))


if __name__ == "__main__":
    # Quick manual test
    cik = get_cik_for_ticker("AAPL")
    print(f"AAPL CIK: {cik}")
    facts = get_company_facts(cik)
    revenue = extract_annual_series(facts, "Revenues")
    print("Revenue by fiscal year:", revenue)
