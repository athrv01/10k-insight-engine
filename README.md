# 10-K Insight Engine

Pulls a public company's financial statements straight from SEC EDGAR,
computes liquidity / profitability / leverage / efficiency ratios across
multiple fiscal years, flags any ratio that moved sharply year-over-year,
and (optionally) generates an AI-written analyst note summarizing what's
going on and what's worth digging into further.

This is meant to demonstrate the kind of "AI-augmented analysis" workflow
real research teams are moving toward: automate the data pull and the
first-pass math, then use an LLM to turn structured numbers into a
readable narrative — with a human analyst reviewing and refining from there.

## How it works

```
SEC EDGAR (XBRL) --> edgar_client.py --> ratios.py --> narrative.py --> report
     (raw data)       (fetch + parse)    (compute)     (Claude API)     (JSON + printout)
```

1. **`edgar_client.py`** — looks up a company's CIK from its ticker, then
   pulls its full XBRL "company facts" (every financial line item it has
   ever reported, tagged by fiscal year) from SEC's free public API. No
   API key needed for this part.
2. **`ratios.py`** — computes 10 standard ratios per fiscal year, then the
   year-over-year % change in each, and flags any that moved past a
   configurable threshold (default 20%).
3. **`narrative.py`** — feeds the computed ratios + flags to the Claude
   API and asks for a short, grounded analyst note. Requires an
   `ANTHROPIC_API_KEY`.
4. **`main.py`** — CLI that runs the whole pipeline for a given ticker
   and saves a JSON report to `output/`.

## Setup

```bash
pip install -r requirements.txt
```

Before running for real, open `edgar_client.py` and replace the
placeholder email in `BASE_HEADERS` with your own — SEC requires a real
contact in the User-Agent string.

If you want the AI narrative step, set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

(Get one at https://console.anthropic.com/)

## Usage

```bash
# Full pipeline, including AI narrative
python main.py AAPL

# Just the data + ratios, no API key needed
python main.py MSFT --no-narrative
```

Output is printed to the console and saved as
`output/<TICKER>_report.json`.

## Testing the logic without hitting SEC or Anthropic

```bash
python test_ratios.py
```

This runs the ratio engine against realistic mock financial data so you
can verify the math independently of live network calls.

## Ratios computed

| Category      | Ratios |
|---------------|--------|
| Liquidity     | Current ratio, Quick ratio |
| Profitability | Gross margin, Operating margin, Net margin, ROE, ROA |
| Leverage      | Debt-to-equity, Interest coverage |
| Efficiency    | Asset turnover |

## Possible extensions

- Add a `--compare TICKER1,TICKER2` mode to run the same analysis across
  multiple companies side by side
- Export to Excel with conditional formatting on flagged ratios instead
  of (or alongside) JSON
- Add a simple Streamlit front-end so it's not CLI-only
- Cache SEC responses locally so repeated runs don't re-hit the API
- Extend `REQUIRED_TAGS` / ratio set to cover DuPont analysis (breaking
  ROE into margin × turnover × leverage)

## Notes on the SEC EDGAR data

- The API is free and requires no authentication — just a descriptive
  User-Agent header.
- `extract_annual_series()` only keeps figures tagged as full fiscal-year
  10-K filings, so quarterly noise is filtered out automatically.
- Some companies use slightly different XBRL tags for the same concept
  (e.g. `Revenues` vs `RevenueFromContractWithCustomerExcludingAssessedTax`).
  `ratios.py` already falls back between the two most common revenue tags;
  if a ratio comes back `None` for a given company, it usually means that
  company reports under a tag not yet handled — check the raw
  `facts["us-gaap"]` keys in the company-facts JSON to find the right one.
