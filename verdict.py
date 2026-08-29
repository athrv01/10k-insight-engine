"""
verdict.py
----------
Turns computed ratios + flagged anomalies into ONE simple overall verdict:
"Healthy", "Mixed Signals", or "Watch Closely".

This is deliberately coarse — it's not meant to replace the detailed
rule-based narrative, it's meant to be a single label that's easy to save
alongside a stock price and compare against later ("you flagged this
Healthy, here's what actually happened to the price since").
"""

def compute_verdict(ratio_series: dict, flags: dict) -> dict:
    """
    Returns {"label": str, "score": int, "reasons": [str, ...]}
    score ranges roughly -3 to +3; label is derived from it.
    """
    years = sorted(ratio_series.keys())
    if not years:
        return {"label": "Not enough data", "score": 0, "reasons": []}

    latest = years[-1]
    latest_ratios = ratio_series[latest]
    score = 0
    reasons = []

    # --- Liquidity ---
    current_ratio = latest_ratios.get("current_ratio")
    if current_ratio is not None:
        if current_ratio >= 1.5:
            score += 1
            reasons.append(f"Current ratio ({current_ratio}) comfortably covers short-term liabilities")
        elif current_ratio < 1.0:
            score -= 1
            reasons.append(f"Current ratio ({current_ratio}) is below 1 — short-term liabilities exceed short-term assets")

    # --- Leverage ---
    d_to_e = latest_ratios.get("debt_to_equity")
    if d_to_e is not None:
        if d_to_e <= 1.0:
            score += 1
            reasons.append(f"Debt-to-equity ({d_to_e}) is conservative")
        elif d_to_e > 2.0:
            score -= 1
            reasons.append(f"Debt-to-equity ({d_to_e}) is high — heavy reliance on debt")

    # --- Profitability ---
    net_margin = latest_ratios.get("net_margin")
    roe = latest_ratios.get("roe")
    if net_margin is not None:
        if net_margin > 0.10:
            score += 1
            reasons.append(f"Net margin ({net_margin}) is healthy")
        elif net_margin < 0:
            score -= 1
            reasons.append("Net margin is negative — the company lost money last fiscal year")
    if roe is not None and roe < 0:
        score -= 1
        reasons.append("Return on equity is negative")

    # --- Anomaly load ---
    total_flags = sum(len(v) for v in flags.values())
    if total_flags >= 4:
        score -= 1
        reasons.append(f"{total_flags} ratios moved sharply year-over-year — worth digging into before trusting the latest numbers")

    # --- Map score to label ---
    if score >= 2:
        label = "Looks Healthy"
    elif score <= -2:
        label = "Watch Closely"
    else:
        label = "Mixed Signals"

    return {"label": label, "score": score, "reasons": reasons}
