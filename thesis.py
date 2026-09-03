"""
thesis.py
---------
"Did your reasoning still hold?" — the sharper follow-up to just tracking
price movement (storage.py already does that). This re-fetches a saved
company's CURRENT financials, recomputes the verdict, and compares it
against what was true at save-time — so a saved analysis can tell you
not just "the price moved," but "the actual fundamentals that justified
your read have changed."

This is genuinely different from a price alert (which any broker app
already gives you) — it's a fundamentals alert, tied to the specific
reasoning you saved.
"""

from ratios import REQUIRED_TAGS, compute_ratios, year_over_year_changes, flag_anomalies
from verdict import compute_verdict


def refetch_current_ratios(ticker: str, exchange: str):
    """
    Re-runs the full data pipeline for a ticker to get its CURRENT ratio
    series (not the snapshot saved earlier). Returns (ratio_series, flags)
    or (None, None) if the fetch fails.
    """
    try:
        if exchange == "US":
            from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series
            cik = get_cik_for_ticker(ticker)
            facts = get_company_facts(cik)
            data = {tag: extract_annual_series(facts, tag) for tag in REQUIRED_TAGS}
        else:
            from nse_bse_client import get_company_facts as get_nse_bse_facts
            _, data = get_nse_bse_facts(ticker, exchange)

        ratio_series = compute_ratios(data)
        changes = year_over_year_changes(ratio_series)
        flags = flag_anomalies(changes, threshold_pct=20.0)
        return ratio_series, flags
    except Exception:
        return None, None


# Which ratios matter for thesis tracking, and what a "meaningful" shift
# in each looks like — deliberately mirrors the bands in
# rule_based_narrative.py, so the story stays consistent everywhere.
TRACKED_RATIOS = {
    "current_ratio": {"label": "Current ratio", "bands": [(1.0, "below 1.0"), (2.0, "1.0-2.0"), (float("inf"), "above 2.0")]},
    "debt_to_equity": {"label": "Debt-to-equity", "bands": [(0.5, "conservative (<0.5)"), (1.5, "moderate (0.5-1.5)"), (float("inf"), "aggressive (>1.5)")]},
    "net_margin": {"label": "Net margin", "bands": [(0.0, "negative"), (0.10, "0-10%"), (float("inf"), "above 10%")]},
}


def _band_index(value, bands):
    if value is None:
        return None
    for i, (upper, _) in enumerate(bands):
        if value <= upper:
            return i
    return len(bands) - 1


def compare_thesis(old_ratio_series: dict, old_verdict_label: str, new_ratio_series: dict, new_flags: dict) -> dict:
    """
    Returns a dict describing whether the saved thesis still holds:
    {
        "status": "no_new_data" | "holding" | "weakening" | "strengthening",
        "new_verdict": {...},
        "old_verdict_label": str,
        "shifts": [str, ...],   # plain-English description of what changed band, if anything
        "old_latest_fy": int or None,
        "new_latest_fy": int or None,
    }
    """
    # Defensive: fiscal-year keys may arrive as strings if a caller passed
    # data straight from a JSON round-trip (JSON object keys are always
    # strings). Normalize to int here so year comparisons below can't
    # silently break regardless of how this function gets called.
    old_ratio_series = {int(fy): ratios for fy, ratios in old_ratio_series.items()}
    new_ratio_series = {int(fy): ratios for fy, ratios in new_ratio_series.items()}

    old_years = sorted(old_ratio_series.keys())
    new_years = sorted(new_ratio_series.keys())

    old_latest_fy = old_years[-1] if old_years else None
    new_latest_fy = new_years[-1] if new_years else None

    if not new_years:
        return {
            "status": "no_new_data",
            "new_verdict": None,
            "old_verdict_label": old_verdict_label,
            "shifts": [],
            "old_latest_fy": old_latest_fy,
            "new_latest_fy": new_latest_fy,
        }

    new_verdict = compute_verdict(new_ratio_series, new_flags)

    # Describe any ratio that moved into a different "band" since the save
    shifts = []
    if old_latest_fy is not None and new_latest_fy is not None:
        old_latest = old_ratio_series.get(old_latest_fy, {})
        new_latest = new_ratio_series.get(new_latest_fy, {})

        for key, meta in TRACKED_RATIOS.items():
            old_val = old_latest.get(key)
            new_val = new_latest.get(key)
            old_band = _band_index(old_val, meta["bands"])
            new_band = _band_index(new_val, meta["bands"])
            if old_band is not None and new_band is not None and old_band != new_band:
                old_desc = meta["bands"][old_band][1]
                new_desc = meta["bands"][new_band][1]
                shifts.append(
                    f"{meta['label']} moved from {old_desc} (FY{old_latest_fy}) to {new_desc} (FY{new_latest_fy})"
                )

    has_new_filing = old_latest_fy is not None and new_latest_fy is not None and new_latest_fy > old_latest_fy

    if not has_new_filing:
        status = "no_new_data"
    elif new_verdict["label"] == old_verdict_label:
        status = "holding" if not shifts else "holding_with_moves"
    else:
        # Crude but reasonable: Healthy -> Mixed/Watch is weakening; Watch -> Mixed/Healthy is strengthening
        rank = {"Looks Healthy": 2, "Mixed Signals": 1, "Watch Closely": 0}
        old_rank = rank.get(old_verdict_label, 1)
        new_rank = rank.get(new_verdict["label"], 1)
        status = "strengthening" if new_rank > old_rank else "weakening"

    return {
        "status": status,
        "new_verdict": new_verdict,
        "old_verdict_label": old_verdict_label,
        "shifts": shifts,
        "old_latest_fy": old_latest_fy,
        "new_latest_fy": new_latest_fy,
    }


STATUS_MESSAGES = {
    "no_new_data": "No new annual filing since you saved this — the thesis is based on the same data as before.",
    "holding": "Your original read still holds — the latest filing shows the same overall picture.",
    "holding_with_moves": "The overall verdict is unchanged, but some underlying ratios have shifted — worth a look.",
    "weakening": "Your original thesis may be weakening — the latest filing paints a less favorable picture than when you saved this.",
    "strengthening": "Things have improved since you saved this — the latest filing looks stronger than your original read.",
}
