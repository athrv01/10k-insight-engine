"""
main.py
-------
10-K Insight Engine — CLI entry point.

Usage:
    python main.py AAPL                        # US ticker via SEC EDGAR (default)
    python main.py RELIANCE --exchange NSE      # Indian ticker via NSE (Yahoo Finance)
    python main.py 500325 --exchange BSE        # Indian ticker via BSE (Yahoo Finance)
    python main.py MSFT --ai-narrative          # use Claude API instead (needs ANTHROPIC_API_KEY)
    python main.py TSLA --no-narrative          # skip narrative generation entirely

Pipeline:
    1. Fetch raw financial data — SEC EDGAR for US tickers, Yahoo Finance
       for NSE/BSE tickers
    2. Compute ratios per fiscal year
    3. Compute year-over-year % changes and flag big moves
    4. Generate an analyst narrative — rule-based by default, or via the
       Claude API if --ai-narrative is passed
    5. Print + save a report

NOTE on NSE/BSE: SEC EDGAR only covers US-listed companies, so Indian
tickers are pulled from Yahoo Finance instead via nse_bse_client.py.
Yahoo's data schema is less standardized than SEC's — if a ratio comes
back missing for an NSE/BSE ticker, run debug_nse_bse.py to see what
Yahoo actually returned.
"""

import argparse
import json
import os

from ratios import REQUIRED_TAGS, compute_ratios, year_over_year_changes, flag_anomalies


def run(ticker: str, exchange: str = "US", generate_narrative_flag: bool = True, use_ai: bool = False):
    cik = None

    if exchange == "US":
        from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series

        print(f"Looking up CIK for {ticker}...")
        cik = get_cik_for_ticker(ticker)

        print(f"Pulling SEC company facts for CIK {cik}...")
        facts = get_company_facts(cik)
        company_name = facts.get("entityName", ticker)

        print("Extracting financial line items...")
        data = {tag: extract_annual_series(facts, tag) for tag in REQUIRED_TAGS}
    else:
        from nse_bse_client import get_company_facts as get_nse_bse_facts

        print(f"Pulling {ticker} from Yahoo Finance ({exchange})...")
        company_name, data = get_nse_bse_facts(ticker, exchange)

    print("Computing ratios...")
    ratio_series = compute_ratios(data)

    print("Computing year-over-year changes...")
    changes = year_over_year_changes(ratio_series)
    flags = flag_anomalies(changes, threshold_pct=20.0)

    report = {
        "company": company_name,
        "ticker": ticker.upper(),
        "exchange": exchange,
        "ratios_by_year": ratio_series,
        "year_over_year_pct_change": changes,
        "flagged_anomalies": flags,
    }
    if cik:
        report["cik"] = cik

    if generate_narrative_flag:
        if use_ai:
            try:
                from narrative import generate_narrative
                print("Generating AI analyst narrative (Claude API)...")
                report["narrative"] = generate_narrative(company_name, ratio_series, flags)
                report["narrative_source"] = "ai"
            except EnvironmentError as e:
                print(f"[Falling back to rule-based] {e}")
                use_ai = False

        if not use_ai:
            from rule_based_narrative import generate_narrative
            print("Generating rule-based analyst narrative (free, no API key)...")
            report["narrative"] = generate_narrative(company_name, ratio_series, flags)
            report["narrative_source"] = "rule_based"

    os.makedirs("output", exist_ok=True)
    out_path = f"output/{ticker.upper()}_report.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nDone. Full report saved to {out_path}\n")
    print("=" * 60)
    print(f"{company_name} ({ticker.upper()}, {exchange}) — Summary")
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
        label = "AI ANALYST NOTE" if report.get("narrative_source") == "ai" else "ANALYST NOTE (rule-based)"
        print("\n" + "-" * 60)
        print(label)
        print("-" * 60)
        print(report["narrative"])

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="10-K Insight Engine")
    parser.add_argument("ticker", help="Stock ticker, e.g. AAPL, RELIANCE, 500325")
    parser.add_argument(
        "--exchange", choices=["US", "NSE", "BSE"], default="US",
        help="Which exchange/data source to use (default: US via SEC EDGAR)"
    )
    parser.add_argument(
        "--no-narrative", action="store_true",
        help="Skip narrative generation entirely"
    )
    parser.add_argument(
        "--ai-narrative", action="store_true",
        help="Use the Claude API for the narrative instead of the free rule-based engine (needs ANTHROPIC_API_KEY)"
    )
    args = parser.parse_args()

    run(args.ticker, exchange=args.exchange, generate_narrative_flag=not args.no_narrative, use_ai=args.ai_narrative)
