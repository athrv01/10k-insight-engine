"""
test_ratios.py
---------------
Sanity-checks ratios.py against realistic mock financials (modeled loosely
on a large-cap tech company's actual reported order of magnitude) so we
can confirm the math is correct without needing live SEC access.
"""

from ratios import compute_ratios, year_over_year_changes, flag_anomalies

mock_data = {
    "Assets": {2022: 352_755_000_000, 2023: 352_583_000_000, 2024: 364_980_000_000},
    "AssetsCurrent": {2022: 135_405_000_000, 2023: 143_566_000_000, 2024: 152_987_000_000},
    "LiabilitiesCurrent": {2022: 153_982_000_000, 2023: 145_308_000_000, 2024: 176_392_000_000},
    "Liabilities": {2022: 302_083_000_000, 2023: 290_437_000_000, 2024: 308_030_000_000},
    "StockholdersEquity": {2022: 50_672_000_000, 2023: 62_146_000_000, 2024: 56_950_000_000},
    "Revenues": {2022: 394_328_000_000, 2023: 383_285_000_000, 2024: 391_035_000_000},
    "CostOfGoodsAndServicesSold": {2022: 223_546_000_000, 2023: 214_137_000_000, 2024: 210_352_000_000},
    "NetIncomeLoss": {2022: 99_803_000_000, 2023: 96_995_000_000, 2024: 93_736_000_000},
    "GrossProfit": {2022: 170_782_000_000, 2023: 169_148_000_000, 2024: 180_683_000_000},
    "OperatingIncomeLoss": {2022: 119_437_000_000, 2023: 114_301_000_000, 2024: 123_216_000_000},
    "InterestExpense": {2022: 2_931_000_000, 2023: 3_933_000_000, 2024: 3_997_000_000},
    "InventoryNet": {2022: 4_946_000_000, 2023: 6_331_000_000, 2024: 7_286_000_000},
    "CashAndCashEquivalentsAtCarryingValue": {2022: 23_646_000_000, 2023: 29_965_000_000, 2024: 29_943_000_000},
}

ratio_series = compute_ratios(mock_data)
changes = year_over_year_changes(ratio_series)
flags = flag_anomalies(changes, threshold_pct=15.0)  # lower threshold since mock data is fairly stable

print("=== RATIOS BY YEAR ===")
for fy, ratios in ratio_series.items():
    print(f"\nFY{fy}:")
    for name, val in ratios.items():
        print(f"  {name:20s}: {val}")

print("\n=== YEAR-OVER-YEAR % CHANGE ===")
for fy, ch in changes.items():
    print(f"\nFY{fy} vs prior year:")
    for name, pct in ch.items():
        print(f"  {name:20s}: {pct}%")

print("\n=== FLAGGED ANOMALIES (>=15% move) ===")
if flags:
    for fy, items in flags.items():
        for name, pct in items:
            print(f"  FY{fy}: {name} moved {pct:+.1f}%")
else:
    print("  None")

# Basic assertions to catch logic errors
assert ratio_series[2024]["current_ratio"] > 0, "Current ratio should be positive"
assert ratio_series[2024]["net_margin"] < 1, "Net margin should be a fraction, not raw dollars"
assert 2023 in changes, "Should compute YoY change for 2023"
print("\nAll sanity checks passed.")
