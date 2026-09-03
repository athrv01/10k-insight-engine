"""
rule_based_narrative.py
------------------------
Generates an analyst-style written note purely from deterministic rules
applied to the computed ratios and flagged anomalies — no LLM API call,
no API key, no cost, and fully reproducible (same input always gives the
same output).

This is a drop-in alternative to narrative.py's generate_narrative():
same function signature, same return type (a string), so main.py / app.py
can call either one interchangeably.
"""

# ---------------------------------------------------------------------------
# Threshold tables — tune these if you want stricter/looser classifications.
# ---------------------------------------------------------------------------
CURRENT_RATIO_THRESHOLDS = {"strong": 2.0, "adequate": 1.0}
ROE_THRESHOLDS = {"strong": 0.15, "moderate": 0.05}
DEBT_TO_EQUITY_THRESHOLDS = {"conservative": 0.5, "moderate": 1.5}
INTEREST_COVERAGE_THRESHOLDS = {"strong": 5.0, "adequate": 2.0}
TREND_MEANINGFUL_PCT = 5.0  # % change below this is treated as "stable"

RATIO_LABELS = {
    "current_ratio": "current ratio",
    "quick_ratio": "quick ratio",
    "gross_margin": "gross margin",
    "operating_margin": "operating margin",
    "net_margin": "net margin",
    "roe": "return on equity",
    "roa": "return on assets",
    "debt_to_equity": "debt-to-equity ratio",
    "interest_coverage": "interest coverage",
    "asset_turnover": "asset turnover",
}

# Short, plain-language notes on what commonly drives a move in each ratio —
# used to give "watch items" some substance instead of just repeating the %.
RATIO_WATCH_HINTS = {
    "current_ratio": "often driven by shifts in cash, receivables, or short-term debt",
    "quick_ratio": "similar to the current ratio but strips out inventory — worth checking if inventory itself is building up",
    "gross_margin": "usually reflects pricing power or input/production cost changes",
    "operating_margin": "reflects both gross margin and changes in operating expense discipline",
    "net_margin": "can be affected by one-off items (tax changes, write-offs, gains) as well as core profitability",
    "roe": "sensitive to both net income swings and changes in equity (buybacks, dividends, losses)",
    "roa": "reflects how efficiently the balance sheet is generating profit",
    "debt_to_equity": "check whether this is new borrowing, or equity shrinking (e.g. buybacks, losses)",
    "interest_coverage": "worth checking alongside the debt-to-equity move — servicing new debt is the common cause",
    "asset_turnover": "reflects how efficiently assets are being used to generate revenue",
}


def _latest_valid(ratio_series, key):
    """Return the most recent non-None value for a ratio key."""
    for fy in sorted(ratio_series.keys(), reverse=True):
        val = ratio_series[fy].get(key)
        if val is not None:
            return fy, val
    return None, None


def _trend_direction(ratio_series, key):
    """
    Compare the earliest vs latest available value for a ratio and
    classify the trend as improving / deteriorating / stable.
    Returns (direction, pct_change) or (None, None) if not enough data.
    """
    years = sorted(ratio_series.keys())
    values = [(fy, ratio_series[fy].get(key)) for fy in years if ratio_series[fy].get(key) is not None]
    if len(values) < 2:
        return None, None

    (first_fy, first_val), (last_fy, last_val) = values[0], values[-1]
    if first_val == 0:
        return None, None

    pct_change = ((last_val - first_val) / abs(first_val)) * 100
    if abs(pct_change) < TREND_MEANINGFUL_PCT:
        return "stable", pct_change
    return ("improving" if pct_change > 0 else "deteriorating"), pct_change


def _classify_liquidity(ratio_series, latest_fy):
    current_ratio = ratio_series[latest_fy].get("current_ratio")
    if current_ratio is None:
        return "Liquidity data wasn't available for the most recent fiscal year on file."

    if current_ratio >= CURRENT_RATIO_THRESHOLDS["strong"]:
        strength = "comfortably covers"
        note = "leaving ample room for short-term obligations"
    elif current_ratio >= CURRENT_RATIO_THRESHOLDS["adequate"]:
        strength = "covers"
        note = "which is adequate but leaves less of a cushion than a more conservative balance sheet"
    else:
        strength = "does not fully cover"
        note = "which is worth flagging — current liabilities exceed current assets"

    return (
        f"The current ratio of {current_ratio} {strength} short-term liabilities, {note}."
    )


def _classify_leverage(ratio_series, latest_fy):
    d_to_e = ratio_series[latest_fy].get("debt_to_equity")
    coverage = ratio_series[latest_fy].get("interest_coverage")
    parts = []

    if d_to_e is not None:
        if d_to_e <= DEBT_TO_EQUITY_THRESHOLDS["conservative"]:
            parts.append(f"Debt-to-equity sits at a conservative {d_to_e}.")
        elif d_to_e <= DEBT_TO_EQUITY_THRESHOLDS["moderate"]:
            parts.append(f"Debt-to-equity is moderate at {d_to_e}.")
        else:
            parts.append(f"Debt-to-equity is elevated at {d_to_e}, indicating meaningful reliance on debt financing.")

    if coverage is not None:
        if coverage < 0:
            parts.append(
                f"Interest coverage is negative ({coverage}) — this means operating income itself is "
                f"negative, not just thin coverage. The company isn't earning enough from operations "
                f"alone to cover interest, separate from whether it's covering it some other way (cash "
                f"reserves, new financing, etc.)."
            )
        elif coverage >= INTEREST_COVERAGE_THRESHOLDS["strong"]:
            parts.append(f"Interest coverage of {coverage} suggests operating income comfortably covers interest expense.")
        elif coverage >= INTEREST_COVERAGE_THRESHOLDS["adequate"]:
            parts.append(f"Interest coverage of {coverage} is adequate but not generous.")
        else:
            parts.append(f"Interest coverage of {coverage} is thin — worth watching if earnings soften.")

    return " ".join(parts) if parts else "Leverage data wasn't available for the most recent fiscal year."


def _classify_profitability(ratio_series):
    direction, pct_change = _trend_direction(ratio_series, "net_margin")
    latest_fy, latest_margin = _latest_valid(ratio_series, "net_margin")
    _, latest_roe = _latest_valid(ratio_series, "roe")

    if latest_fy is None:
        return "Profitability data wasn't available across the fiscal years on file."

    sentence = f"Net margin stands at {latest_margin} as of FY{latest_fy}"
    if direction == "improving":
        sentence += f", up {abs(pct_change):.1f}% from the earliest year on file — a genuinely improving trend."
    elif direction == "deteriorating":
        sentence += f", down {abs(pct_change):.1f}% from the earliest year on file — a trend worth digging into."
    elif direction == "stable":
        sentence += ", roughly flat over the period on file."
    else:
        sentence += "."

    if latest_roe is not None:
        if latest_roe >= ROE_THRESHOLDS["strong"]:
            sentence += f" Return on equity of {latest_roe} is strong."
        elif latest_roe >= ROE_THRESHOLDS["moderate"]:
            sentence += f" Return on equity of {latest_roe} is moderate."
        else:
            sentence += f" Return on equity of {latest_roe} is low relative to typical benchmarks."

    return sentence


def _build_overview(company_name, ratio_series):
    years = sorted(ratio_series.keys())
    latest_fy = years[-1]
    span = f"FY{years[0]}–FY{years[-1]}" if len(years) > 1 else f"FY{years[0]}"

    _, net_margin = _latest_valid(ratio_series, "net_margin")
    _, roa = _latest_valid(ratio_series, "roa")

    overview = f"{company_name} reported financial data spanning {span}."
    if net_margin is not None:
        overview += f" As of FY{latest_fy}, net margin was {net_margin}"
        if roa is not None:
            overview += f" and return on assets was {roa}."
        else:
            overview += "."
    return overview


def _build_watch_items(flags, has_multi_year_data=True, max_items=4):
    flat = []
    for fy, items in flags.items():
        for name, pct in items:
            flat.append((fy, name, pct))

    if not flat:
        if not has_multi_year_data:
            return (
                "No year-over-year comparison is possible yet — only one fiscal year of filings "
                "exists for this company (common for a recent IPO or a newly-covered small-cap). "
                "The ratios above reflect a single snapshot, not a trend, so there's nothing (yet) "
                "to flag as having 'moved' — that's different from everything being confirmed stable."
            )
        return "No ratios moved sharply enough year-over-year to flag for further review at the configured threshold."

    # Prioritize the largest moves
    flat.sort(key=lambda x: -abs(x[2]))
    lines = []
    for fy, name, pct in flat[:max_items]:
        label = RATIO_LABELS.get(name, name)
        hint = RATIO_WATCH_HINTS.get(name, "")
        direction = "increased" if pct > 0 else "decreased"
        line = f"- {label.capitalize()} {direction} {abs(pct):.1f}% in FY{fy}"
        if hint:
            line += f" — {hint}."
        else:
            line += "."
        lines.append(line)

    return "\n".join(lines)


def generate_narrative(company_name: str, ratio_series: dict, flags: dict) -> str:
    """
    Same signature as narrative.generate_narrative() so it's a drop-in
    replacement — no API key, no network call, deterministic output.
    """
    years = sorted(ratio_series.keys())
    if not years:
        return f"No ratio data was available for {company_name}."

    latest_fy = years[-1]
    has_multi_year_data = len(years) >= 2

    overview = _build_overview(company_name, ratio_series)
    if not has_multi_year_data:
        overview += (
            f" Note: only FY{latest_fy} is on file for this company — likely a recent IPO or a "
            f"company with limited filing history. Everything below is a single-year snapshot, not "
            f"a trend; treat it as a starting baseline rather than a full picture."
        )

    liquidity = _classify_liquidity(ratio_series, latest_fy)
    leverage = _classify_leverage(ratio_series, latest_fy)
    profitability = _classify_profitability(ratio_series)
    watch_items = _build_watch_items(flags, has_multi_year_data)

    return f"""{overview}

**Liquidity & leverage:** {liquidity} {leverage}

**Profitability:** {profitability}

**Worth digging into further:**
{watch_items}

*This note was generated by rule-based logic applied directly to the computed ratios above — no AI model was used, so treat it as a structured first pass rather than analyst judgment.*"""
