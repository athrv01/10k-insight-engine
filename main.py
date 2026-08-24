"""
main.py
-------
10-K Insight Engine — CLI entry point.

Usage:
    python main.py AAPL
    python main.py MSFT --no-narrative   # skip the Claude API call (free run)

Pipeline:
    1. Look up CIK for the ticker
    2. Pull raw XBRL company facts from SEC EDGAR
    3. Extract the line items we need
    4. Compute ratios per fiscal year
    5. Compute year-over-year % changes and flag big moves
    6. (optional) Generate an AI analyst narrative
    7. Print + save a report
"""

import argparse
import json
import os

from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series
from ratios import REQUIRED_TAGS, compute_ratios, year_over_year_changes, flag_anomalies


def run(ticker: str, generate_narrative_flag: bool = True):
    print(f"Looking up CIK for {ticker}...")
    cik = get_cik_for_ticker(ticker)

    print(f"Pulling SEC company facts for CIK {cik}...")
    facts = get_company_facts(cik)
    company_name = facts.get("entityName", ticker)

    print("Extracting financial line items...")
    data = {tag: extract_annual_series(facts, tag) for tag in REQUIRED_TAGS}

    print("Computing ratios...")
    ratio_series = compute_ratios(data)

    print("Computing year-over-year changes...")
    changes = year_over_year_changes(ratio_series)
    flags = flag_anomalies(changes, threshold_pct=20.0)

    report = {
        "company": company_name,
        "ticker": ticker.upper(),
        "cik": cik,
        "ratios_by_year": ratio_series,
        "year_over_year_pct_change": changes,
        "flagged_anomalies": flags,
    }

    if generate_narrative_flag:
        try:
            from narrative import generate_narrative
            print("Generating AI analyst narrative...")
            report["narrative"] = generate_narrative(company_name, ratio_series, flags)
        except EnvironmentError as e:
            print(f"[Skipping narrative] {e}")

    os.makedirs("output", exist_ok=True)
    out_path = f"output/{ticker.upper()}_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDone. Full report saved to {out_path}\n")
    print("=" * 60)
    print(f"{company_name} ({ticker.upper()}) — Summary")
    print("=" * 60)

    years = sorted(ratio_series.keys())
    if years:
        latest = years[-1]
        print(f"Latest fiscal year: {latest}")
        for k, v in ratio_series[latest].items():
            print(f"  {k:20s}: {v}")

    if flags:
        print("\nFlagged year-over-year moves (>=20%):")
        for fy, items in flags.items():
            for name, pct in items:
                print(f"  FY{fy}: {name} moved {pct:+.1f}%")

    if "narrative" in report:
        print("\n" + "-" * 60)
        print("AI ANALYST NOTE")
        print("-" * 60)
        print(report["narrative"])

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="10-K Insight Engine")
    parser.add_argument("ticker", help="Stock ticker, e.g. AAPL")
    parser.add_argument(
        "--no-narrative", action="store_true",
        help="Skip the Claude API call (no API key needed)"
    )
    args = parser.parse_args()

    run(args.ticker, generate_narrative_flag=not args.no_narrative)
