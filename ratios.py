"""
ratios.py
---------
Computes standard financial ratios (liquidity, profitability, leverage,
efficiency) from raw US-GAAP line items pulled via edgar_client.py.

Design: each ratio function takes a dict of {concept_name: {fy: value}}
and returns a {fy: ratio_value} series, so everything lines up by year
and can be diffed year-over-year later.
"""

# US-GAAP tags we need from SEC EDGAR for the ratios below.
REQUIRED_TAGS = [
    "Assets",
    "AssetsCurrent",
    "LiabilitiesCurrent",
    "Liabilities",
    "StockholdersEquity",
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",  # newer tag some filers use instead of Revenues
    "CostOfGoodsAndServicesSold",
    "NetIncomeLoss",
    "GrossProfit",
    "OperatingIncomeLoss",
    "InterestExpense",
    "InventoryNet",
    "CashAndCashEquivalentsAtCarryingValue",
]


def _get(data, tag, fy):
    return data.get(tag, {}).get(fy)


def _safe_div(a, b):
    if a is None or b in (None, 0):
        return None
    return round(a / b, 3)


def compute_ratios(data: dict) -> dict:
    """
    data: {us_gaap_tag: {fiscal_year: value}}
    returns: {fiscal_year: {ratio_name: value}}
    """
    # Union of all fiscal years we have any data for
    years = sorted({fy for series in data.values() for fy in series})

    results = {}
    for fy in years:
        current_assets = _get(data, "AssetsCurrent", fy)
        current_liabilities = _get(data, "LiabilitiesCurrent", fy)
        total_assets = _get(data, "Assets", fy)
        total_liabilities = _get(data, "Liabilities", fy)
        equity = _get(data, "StockholdersEquity", fy)
        revenue = _get(data, "Revenues", fy) or _get(
            data, "RevenueFromContractWithCustomerExcludingAssessedTax", fy
        )
        cogs = _get(data, "CostOfGoodsAndServicesSold", fy)
        net_income = _get(data, "NetIncomeLoss", fy)
        gross_profit = _get(data, "GrossProfit", fy)
        operating_income = _get(data, "OperatingIncomeLoss", fy)
        interest_expense = _get(data, "InterestExpense", fy)
        inventory = _get(data, "InventoryNet", fy)
        cash = _get(data, "CashAndCashEquivalentsAtCarryingValue", fy)

        results[fy] = {
            # --- Liquidity ---
            "current_ratio": _safe_div(current_assets, current_liabilities),
            "quick_ratio": _safe_div(
                (current_assets - inventory) if (current_assets and inventory is not None) else current_assets,
                current_liabilities,
            ),

            # --- Profitability ---
            "gross_margin": _safe_div(gross_profit, revenue),
            "operating_margin": _safe_div(operating_income, revenue),
            "net_margin": _safe_div(net_income, revenue),
            "roe": _safe_div(net_income, equity),
            "roa": _safe_div(net_income, total_assets),

            # --- Leverage ---
            "debt_to_equity": _safe_div(total_liabilities, equity),
            "interest_coverage": _safe_div(operating_income, interest_expense),

            # --- Efficiency ---
            "asset_turnover": _safe_div(revenue, total_assets),
        }

    return results


def year_over_year_changes(ratio_series: dict) -> dict:
    """
    Given {fy: {ratio: value}}, compute the % change of each ratio
    from the prior year. Used to flag anomalies.
    """
    years = sorted(ratio_series.keys())
    changes = {}

    for i in range(1, len(years)):
        prev_year, curr_year = years[i - 1], years[i]
        prev, curr = ratio_series[prev_year], ratio_series[curr_year]
        changes[curr_year] = {}

        for ratio_name, curr_val in curr.items():
            prev_val = prev.get(ratio_name)
            if prev_val in (None, 0) or curr_val is None:
                changes[curr_year][ratio_name] = None
            else:
                pct_change = round((curr_val - prev_val) / abs(prev_val) * 100, 1)
                changes[curr_year][ratio_name] = pct_change

    return changes


def flag_anomalies(changes: dict, threshold_pct: float = 20.0) -> dict:
    """
    Flag any ratio that moved more than `threshold_pct` year-over-year.
    Returns {fy: [(ratio_name, pct_change), ...]}
    """
    flags = {}
    for fy, ratio_changes in changes.items():
        year_flags = [
            (name, pct) for name, pct in ratio_changes.items()
            if pct is not None and abs(pct) >= threshold_pct
        ]
        if year_flags:
            flags[fy] = sorted(year_flags, key=lambda x: -abs(x[1]))
    return flags
