"""
app.py
------
Streamlit web front-end for the 10-K Insight Engine.
Dark editorial finance interface inspired by a bold, image-led creative studio landing page,
with the existing 10-K analysis pipeline and per-metric area sparklines preserved.

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series
from ratios import REQUIRED_TAGS, compute_ratios, year_over_year_changes, flag_anomalies

st.set_page_config(
    page_title="10-K Insight Engine",
    page_icon="◉",
    layout="wide",
)

# ---------------------------------------------------------------------------
# STYLING — light mode, slate + blue/emerald/amber accents
# ---------------------------------------------------------------------------
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=DM+Mono:wght@400;500&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --ink: #080808;
    --panel: #1b1b1d;
    --panel-2: #232326;
    --paper: #f2f1e8;
    --orange: #ff5a1f;
    --orange-dark: #b63d17;
    --muted: #8e8b86;
    --line: #3a3734;
    --blue: #4b91dc;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: var(--ink); color: var(--paper); }
.main .block-container { max-width: 1380px; padding: 1.2rem 2.2rem 4rem; }
header[data-testid="stHeader"] { background: transparent; }
footer { visibility: hidden; }

/* Hide the default Streamlit sidebar: controls live in the editorial header. */
section[data-testid="stSidebar"] { display: none; }

/* Global typography */
h1,h2,h3,h4 { color: var(--paper) !important; }
.stMarkdown p, .stMarkdown li, .stCaption { color: #bdb9b2 !important; }

.editorial-shell {
    background: var(--panel);
    border: 1px solid #252527;
    border-radius: 22px;
    overflow: hidden;
    box-shadow: 0 24px 80px rgba(0,0,0,.38);
}

.topbar {
    display:flex; align-items:center; justify-content:space-between;
    padding: 1.15rem 1.55rem .9rem;
    font-family:'DM Mono', monospace; font-size:.64rem;
    text-transform:uppercase; letter-spacing:.03em;
}
.brand { color: var(--orange) !important; font-weight:700; }
.top-links { display:flex; gap:1.25rem; color:#a7a39d; }
.top-links span { color:#a7a39d !important; }

.hero {
    position:relative; min-height:500px; padding:2.7rem 2.2rem 3.1rem;
    display:flex; align-items:center; justify-content:center; overflow:hidden;
}
.hero-title {
    position:relative; z-index:3; width:min(760px, 75%);
    margin:0 auto; text-align:center;
    font-family:'Anton', Impact, sans-serif !important;
    font-size:clamp(4.3rem, 8vw, 7.8rem); line-height:.84;
    letter-spacing:-.025em; text-transform:uppercase;
    color:var(--orange) !important; font-weight:400;
    transform:skew(-5deg);
}
.hero-title .line { display:block; }
.hero-title .italic { font-style:italic; }
.hero-sub {
    position:relative; z-index:4; max-width:620px; margin:1.8rem auto 0;
    text-align:center; color:#a7a39d !important; font-size:.84rem;
}

.visual-card {
    position:absolute; z-index:2; width:165px; height:255px;
    border:1px solid #514b45; background:linear-gradient(145deg,#8b5f43,#d7b58a 45%,#3b2a24);
    box-shadow:0 18px 40px rgba(0,0,0,.32);
    overflow:hidden;
}
.visual-card::before { content:""; position:absolute; inset:0; background:linear-gradient(145deg,rgba(255,255,255,.14),transparent 45%,rgba(0,0,0,.28)); }
.visual-card::after { content:"10-K"; position:absolute; bottom:12px; left:12px; font-family:'DM Mono'; font-size:.65rem; color:#f4ede4; letter-spacing:.12em; }
.visual-left { left:4%; top:13%; transform:rotate(-2deg); }
.visual-right { right:4%; bottom:12%; width:205px; height:130px; background:linear-gradient(145deg,#b84b24,#ff7b3d 42%,#2a2020); transform:rotate(1.5deg); }
.visual-right::after { content:"SEC / EDGAR"; }

.cta-row { position:relative; z-index:5; display:flex; justify-content:center; margin-top:1.6rem; }
.stButton>button {
    background:transparent !important; color:var(--orange) !important;
    border:1px solid var(--orange-dark) !important; border-radius:999px !important;
    min-height:44px; padding:0 2.2rem !important; font-family:'DM Mono',monospace !important;
    text-transform:uppercase; letter-spacing:.05em; font-size:.68rem !important;
    transition:.2s ease;
}
.stButton>button:hover { background:var(--orange) !important; color:#111 !important; border-color:var(--orange) !important; transform:translateY(-1px); }
.stButton>button p { color:inherit !important; }

.ticker-strip {
    border-top:1px solid #34302d; border-bottom:1px solid #34302d;
    overflow:hidden; white-space:nowrap; padding:.55rem 0;
    font-family:'DM Mono',monospace; font-size:.54rem; color:#9e5540;
    text-transform:uppercase; letter-spacing:.08em;
}
.ticker-strip span { margin-right:2.5rem; }

.control-panel {
    background:#141416; border:1px solid #302e2d; border-radius:16px;
    padding:1rem 1.1rem; margin:1rem 0 1.2rem;
}
.control-label { font-family:'DM Mono'; text-transform:uppercase; font-size:.58rem; color:#8c8780 !important; letter-spacing:.08em; margin-bottom:.4rem; }
.stTextInput input, .stNumberInput input {
    background:#202023 !important; color:var(--paper) !important; border:1px solid #3a3734 !important;
    border-radius:9px !important;
}
.stSlider [data-baseweb="slider"] { padding-top:.25rem; }
.stSlider label, .stTextInput label { color:#99948d !important; }

/* Dashboard cards */
.card {
    background:#1b1b1d; border:1px solid #2c2b2d; border-radius:16px;
    padding:1.35rem; box-shadow:none; margin-bottom:1.15rem;
}
.eyebrow { text-transform:uppercase; letter-spacing:.09em; font-family:'DM Mono',monospace;
    font-size:.58rem; font-weight:500; color:#8f8a83 !important; margin-bottom:.35rem; }
.headline { font-family:'Anton',Impact,sans-serif !important; font-size:2.5rem; line-height:.95; color:var(--orange) !important; text-transform:uppercase; letter-spacing:.01em; }
.big-stat { font-family:'Anton',Impact,sans-serif; font-size:2.4rem; color:var(--paper) !important; text-align:right; }
.ratio-card-number { font-family:'Anton',Impact,sans-serif; font-size:2rem; color:var(--paper) !important; }
.ratio-card-caption { font-family:'DM Mono',monospace; font-size:.58rem; color:#77736d !important; }
.yoy-badge { display:inline-flex; padding:.28rem .65rem; border:1px solid #4a403a; border-radius:999px; font-family:'DM Mono'; font-size:.58rem; color:var(--orange) !important; }
.yoy-badge.positive, .yoy-badge.negative { background:transparent; color:var(--orange) !important; }
.flag-row { display:flex; justify-content:space-between; padding:.72rem 0; border-bottom:1px solid #2b2928; }
.flag-label { color:#bcb7af !important; font-size:.82rem; }
.flag-value { font-family:'DM Mono'; font-size:.76rem; }
.flag-value.positive, .flag-value.negative { color:var(--orange) !important; }
.narrative-box { background:#1b1b1d; border:1px solid #2c2b2d; padding:1.35rem; border-radius:16px; line-height:1.7; color:#c1bcb4 !important; }
.streamlit-expanderHeader { background:#1b1b1d !important; border:1px solid #2c2b2d !important; color:var(--paper) !important; border-radius:12px !important; }
[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; }

/* Mobile */
@media (max-width: 800px) {
    .main .block-container { padding: .8rem .8rem 3rem; }
    .hero { min-height:520px; padding:2rem .8rem; }
    .hero-title { width:94%; font-size:clamp(3.6rem,15vw,6rem); }
    .visual-card { opacity:.45; }
    .visual-left { left:-8%; }
    .visual-right { right:-8%; }
    .top-links { gap:.65rem; }
}
</style>
""")

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# EDITORIAL HEADER / CONTROLS
# ---------------------------------------------------------------------------
st.html("""
<div class="editorial-shell">
  <div class="topbar">
    <div class="brand">10-K INSIGHT ENGINE</div>
    <div class="top-links"><span>ABOUT</span><span>ANALYSIS</span><span>SEC / EDGAR</span></div>
  </div>
</div>
""")

if "view" not in st.session_state:
    st.session_state["view"] = "dashboard"

nav_l, nav_r = st.columns([3, 1.4])
with nav_l:
    st.markdown("<div class='control-label'>Your name or email (to save analyses)</div>", unsafe_allow_html=True)
    user_label = st.text_input("User label", placeholder="e.g. your.email@example.com", label_visibility="collapsed")
with nav_r:
    st.markdown("<div class='control-label'>&nbsp;</div>", unsafe_allow_html=True)
    nav_btn_l, nav_btn_r = st.columns(2)
    with nav_btn_l:
        if st.button("Dashboard", use_container_width=True):
            st.session_state["view"] = "dashboard"
    with nav_btn_r:
        if st.button("My Analyses", use_container_width=True):
            st.session_state["view"] = "my_analyses"

if st.session_state["view"] == "dashboard":
    c0, c1, c2, c3 = st.columns([1.0, 1.8, 1.0, 1.0], vertical_alignment="bottom")
    with c0:
        st.markdown("<div class='control-label'>Exchange</div>", unsafe_allow_html=True)
        exchange = st.selectbox("Exchange", ["US (SEC)", "NSE", "BSE"], label_visibility="collapsed")
    with c1:
        st.markdown("<div class='control-label'>Company ticker</div>", unsafe_allow_html=True)
        ticker_placeholder = "AAPL / MSFT / TSLA" if exchange == "US (SEC)" else "RELIANCE / TCS / INFY"
        ticker = st.text_input("Ticker", placeholder=ticker_placeholder, label_visibility="collapsed")
    with c2:
        st.markdown("<div class='control-label'>Anomaly threshold</div>", unsafe_allow_html=True)
        threshold = st.slider("Threshold", 5, 100, 20, label_visibility="collapsed")
    with c3:
        st.markdown("<div class='control-label'>Run</div>", unsafe_allow_html=True)
        run_button = st.button("Analyze →", use_container_width=True)
else:
    run_button = False
    ticker = None

# ---------------------------------------------------------------------------
# HERO
# ---------------------------------------------------------------------------
st.html("""
<div class="editorial-shell">
  <div class="hero">
    <div class="visual-card visual-left"></div>
    <div class="visual-card visual-right"></div>
    <div>
      <div class="hero-title">
        <span class="line italic">Turn your</span>
        <span class="line">filings into</span>
        <span class="line italic">insight</span>
      </div>
      <div class="hero-sub">A sharp, visual read of company fundamentals — pulled from SEC filings and reduced to the ratios and movements that matter.</div>
      <div class="cta-row"><span style="font-family:'DM Mono';font-size:.58rem;color:#7e7972;letter-spacing:.08em;">ENTER A TICKER ABOVE TO GET TO WORK ↗</span></div>
    </div>
  </div>
  <div class="ticker-strip">
    <span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span>
  </div>
</div>
""")

# PIPELINE
# ---------------------------------------------------------------------------
if run_button and ticker:
    source_label = "SEC EDGAR" if exchange == "US (SEC)" else f"Yahoo Finance ({exchange})"
    with st.spinner(f"Pulling {ticker.upper()}'s filings from {source_label}..."):
        try:
            if exchange == "US (SEC)":
                cik = get_cik_for_ticker(ticker)
                facts = get_company_facts(cik)
                company_name = facts.get("entityName", ticker.upper())
                data = {tag: extract_annual_series(facts, tag) for tag in REQUIRED_TAGS}
            else:
                from nse_bse_client import get_company_facts as get_nse_bse_facts
                company_name, data = get_nse_bse_facts(ticker, exchange)

            ratio_series = compute_ratios(data)
            changes = year_over_year_changes(ratio_series)
            flags = flag_anomalies(changes, threshold_pct=threshold)

            st.session_state["company_name"] = company_name
            st.session_state["ratio_series"] = ratio_series
            st.session_state["changes"] = changes
            st.session_state["flags"] = flags
            st.session_state["ticker"] = ticker.upper()
            st.session_state["exchange"] = "US" if exchange == "US (SEC)" else exchange
            # Clear any previously generated AI narrative from a prior ticker
            st.session_state.pop("ai_narrative_text", None)

        except Exception as e:
            st.error(f"Couldn't pull data for '{ticker}' on {exchange}: {e}")
            if exchange != "US (SEC)":
                st.caption(
                    "NSE/BSE data comes from Yahoo Finance, which is less standardized than "
                    "SEC's filings. If this keeps failing, run `python debug_nse_bse.py "
                    f"{ticker.upper()} {exchange}` locally to see what Yahoo actually returned."
                )
            st.stop()


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def render_area_sparkline(values, stroke, fill, width=200, height=48):
    """Colored area sparkline (SVG), matching the recharts AreaChart look."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return "<div style='height:48px;'></div>"
    lo, hi = min(clean), max(clean)
    span = (hi - lo) or 1
    step = width / (len(clean) - 1)
    pts = [(i * step, height - ((v - lo) / span) * height) for i, v in enumerate(clean)]
    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_points = f"0,{height} " + line_points + f" {width},{height}"
    return f"""<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none">
        <polygon points="{area_points}" fill="{fill}" />
        <polyline fill="none" stroke="{stroke}" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round" points="{line_points}" />
    </svg>"""


def yoy_badge(pct):
    cls = "positive" if pct >= 0 else "negative"
    return f"<span class='yoy-badge {cls}'>{pct:+.1f}% YoY</span>"


def flag_row(label, pct):
    cls = "positive" if pct >= 0 else "negative"
    return f"""
    <div class="flag-row">
        <span class="flag-label">{label}</span>
        <span class="flag-value {cls}">{pct:+.1f}%</span>
    </div>
    """


def narrative_to_html(text: str) -> str:
    """
    Converts the narrative's lightweight markdown (**bold**, blank-line
    paragraphs, '- ' bullets) into explicit HTML before it's injected into
    a raw HTML div via st.html(). Relying on a markdown parser to also
    handle markdown-inside-html correctly is exactly the kind of edge case
    that caused stray '</div>' tags to render as visible text elsewhere in
    this app — so we convert explicitly instead of hoping it "just works".
    """
    import re
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    paragraphs = text.strip().split("\n\n")
    html_parts = []
    for para in paragraphs:
        lines = para.split("\n")
        if all(line.strip().startswith("- ") for line in lines if line.strip()):
            items = "".join(f"<li>{line.strip()[2:]}</li>" for line in lines if line.strip())
            html_parts.append(f"<ul style='margin:0.3rem 0; padding-left:1.2rem;'>{items}</ul>")
        else:
            html_parts.append(f"<p style='margin:0 0 0.9rem 0;'>{'<br>'.join(lines)}</p>")
    return "".join(html_parts)


# ---------------------------------------------------------------------------
# MAIN CONTENT
# ---------------------------------------------------------------------------
if st.session_state["view"] == "my_analyses":
    st.html("<div class='eyebrow' style='margin-top:1rem;'>My Analyses</div>")

    if not user_label.strip():
        st.warning("Enter your name or email in the field above to see (or start) your saved analyses.")
    else:
        from storage import list_analyses, get_current_price, delete_analysis

        saved = list_analyses(user_label)
        if not saved:
            st.html("""
            <div class="card" style="max-width:760px;margin:1.2rem auto 0;text-align:center;">
                <div class="headline" style="font-size:1.6rem;">Nothing saved yet</div>
                <p style="margin:1rem 0 0;">Run an analysis on the Dashboard tab, then hit "Save this analysis"
                to start tracking whether your read on a company matched what actually happened to its price.</p>
            </div>
            """)
        else:
            for row in saved:
                current_price = get_current_price(row["ticker"], row["exchange"])
                price_then = row["price_at_save"]
                pct_change = None
                if current_price is not None and price_then:
                    pct_change = ((current_price - price_then) / price_then) * 100

                price_line = "Price data unavailable right now"
                if current_price is not None and price_then:
                    direction = "up" if pct_change >= 0 else "down"
                    price_line = (
                        f"${price_then:,.2f} then → ${current_price:,.2f} now "
                        f"({direction} {abs(pct_change):.1f}%)"
                    )

                saved_date = row["saved_at"][:10]
                col_main, col_del = st.columns([5, 1])
                with col_main:
                    st.html(f"""
                    <div class="card">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.75rem;">
                            <div>
                                <div class="eyebrow">{row['ticker']} · {row['exchange']} · saved {saved_date}</div>
                                <div class="headline" style="font-size:1.4rem;">{row['company_name']}</div>
                                <p style="margin-top:0.5rem;">You flagged this: <strong>{row['verdict_label']}</strong></p>
                                <p style="margin-top:0.25rem;">{price_line}</p>
                            </div>
                        </div>
                    </div>
                    """)
                with col_del:
                    if st.button("Delete", key=f"del_{row['id']}"):
                        delete_analysis(row["id"])
                        st.rerun()

elif "ratio_series" in st.session_state:
    company_name = st.session_state["company_name"]
    ratio_series = st.session_state["ratio_series"]
    flags = st.session_state["flags"]
    ticker_disp = st.session_state["ticker"]
    years = sorted(ratio_series.keys())

    if not years:
        st.warning("No annual 10-K ratio data found for this ticker.")
    else:
        latest = years[-1]
        total_flags = sum(len(v) for v in flags.values())

        # Overall YoY badge based on net margin trend
        margin_values = [ratio_series[y]["net_margin"] for y in years]
        first_val = next((v for v in margin_values if v is not None), None)
        last_val = margin_values[-1]
        overall_pct = None
        if first_val and last_val is not None and first_val != 0:
            overall_pct = ((last_val - first_val) / abs(first_val)) * 100

        # --- Header card ---
        h_l, h_r = st.columns([3, 1.6])
        with h_l:
            st.html(f"""
            <div class="card" style="margin-bottom:1.5rem;">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:1rem;">
                    <div>
                        <div class="eyebrow">Ticker Analysis · {ticker_disp}</div>
                        <div class="headline">{company_name}</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:1.5rem;">
                        <div style="text-align:right;">
                            <div class="eyebrow">Flagged Moves</div>
                            <div class="big-stat">{total_flags}</div>
                        </div>
                        {yoy_badge(overall_pct) if overall_pct is not None else ""}
                    </div>
                </div>
            </div>
            """)

        # --- Verdict card + save button ---
        from verdict import compute_verdict
        verdict = compute_verdict(ratio_series, flags)
        verdict_color = {"Looks Healthy": "#059669", "Mixed Signals": "#d97706", "Watch Closely": "#e11d48"}.get(verdict["label"], "#94a3b8")

        v_l, v_r = st.columns([3, 1.4])
        with v_l:
            st.html(f"""
            <div class="card" style="border-left: 4px solid {verdict_color};">
                <div class="eyebrow">Overall Verdict</div>
                <div class="headline" style="font-size:1.5rem; color:{verdict_color};">{verdict['label']}</div>
                <ul style="margin:0.6rem 0 0; padding-left:1.2rem;">
                    {"".join(f"<li>{r}</li>" for r in verdict["reasons"]) if verdict["reasons"] else "<li>Not enough signal either way — a genuinely mixed picture.</li>"}
                </ul>
            </div>
            """)
        with v_r:
            st.markdown("<div class='control-label'>&nbsp;</div>", unsafe_allow_html=True)
            if st.button("Save this analysis", use_container_width=True):
                if not user_label.strip():
                    st.error("Enter your name or email at the top of the page first.")
                else:
                    from storage import save_analysis, get_current_price
                    with st.spinner("Fetching current price..."):
                        price = get_current_price(ticker_disp, st.session_state["exchange"])
                    if price is None:
                        st.error("Couldn't fetch a current price for this ticker — analysis not saved.")
                    else:
                        save_analysis(
                            user_label, ticker_disp, st.session_state["exchange"],
                            company_name, verdict, price, ratio_series,
                        )
                        st.success(f"Saved at ${price:,.2f}. Check back later on the 'My Analyses' tab.")

        # --- Three ratio cards with colored area sparklines ---
        stat_defs = [
            ("Net Margin", "net_margin", "#2563eb", "#dbeafe"),
            ("ROE", "roe", "#059669", "#d1fae5"),
            ("Current Ratio", "current_ratio", "#d97706", "#fef3c7"),
        ]
        c1, c2, c3 = st.columns(3)
        for col, (label, key, stroke, fill) in zip([c1, c2, c3], stat_defs):
            series_vals = [ratio_series[y][key] for y in years]
            latest_val = ratio_series[latest][key]
            with col:
                st.html(f"""
                <div class="card">
                    <div class="eyebrow">{label}</div>
                    {render_area_sparkline(series_vals, stroke, fill)}
                    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:0.5rem;">
                        <span class="ratio-card-number">{latest_val if latest_val is not None else "—"}</span>
                        <span class="ratio-card-caption">As of FY{latest}</span>
                    </div>
                </div>
                """)

        # --- Flagged year-over-year moves ---
        flat_flags = []
        for fy, items in flags.items():
            for name, pct in items:
                flat_flags.append((f"{name.replace('_', ' ').title()} · FY{fy}", pct))

        rows_html = "".join(flag_row(l, p) for l, p in flat_flags) if flat_flags else f"<div class='flag-label' style='padding:0.5rem 0;'>No ratios moved more than ±{threshold}% year-over-year.</div>"
        st.html(
    f'<div class="card"><div class="eyebrow" style="margin-bottom:0.75rem;">Flagged Year-Over-Year Moves</div>{rows_html}</div>')
       

        # --- Full ratio table ---
        with st.expander("View full ratio table by fiscal year"):
            df = pd.DataFrame(ratio_series).T
            df.index.name = "Fiscal Year"
            st.dataframe(df, use_container_width=True)

        # --- Analyst Note: rule-based by default (free, instant), AI optional ---
        st.markdown("<div class='eyebrow' style='margin-top:0.5rem;'>Analyst Note</div>", unsafe_allow_html=True)

        from rule_based_narrative import generate_narrative as generate_rule_based_narrative
        rule_based_text = generate_rule_based_narrative(company_name, ratio_series, flags)

        # If the user has generated an AI version this session, show that instead
        display_text = st.session_state.get("ai_narrative_text", rule_based_text)
        source_label = "AI-generated (Anthropic)" if "ai_narrative_text" in st.session_state else "Rule-based (free, instant)"

        st.caption(f"Source: {source_label}")
        st.html(f"<div class='narrative-box'>{narrative_to_html(display_text)}</div>")

        with st.expander("Want a deeper AI-written note instead? (uses your Anthropic API key)"):
            key_input = st.text_input(
                "Anthropic API key", type="password",
                value=st.session_state.get("anthropic_key", ""),
                help="Get one at console.anthropic.com. Not stored anywhere except this session.",
            )
            if key_input:
                st.session_state["anthropic_key"] = key_input

            if st.button("Generate AI narrative"):
                if not st.session_state.get("anthropic_key"):
                    st.error("Add your Anthropic API key above first.")
                else:
                    import os
                    os.environ["ANTHROPIC_API_KEY"] = st.session_state["anthropic_key"]
                    with st.spinner("Writing analyst note..."):
                        try:
                            from narrative import generate_narrative as generate_ai_narrative
                            st.session_state["ai_narrative_text"] = generate_ai_narrative(company_name, ratio_series, flags)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Couldn't generate narrative: {e}")

            if "ai_narrative_text" in st.session_state:
                if st.button("Revert to rule-based note"):
                    del st.session_state["ai_narrative_text"]
                    st.rerun()

        st.caption(
            "⚠️ For informational and educational purposes only. This is not "
            "investment advice. Data sourced from SEC EDGAR; verify against "
            "original filings before making any decisions."
        )

else:
    st.html("""
    <div class="card" style="max-width:760px;margin:1.2rem auto 0;text-align:center;">
        <div class="eyebrow">How it works</div>
        <div class="headline" style="font-size:2rem;">One ticker. Every important movement.</div>
        <p style="margin:1rem 0 0;">SEC EDGAR data → annual ratios → year-over-year changes → anomaly flags → optional AI analyst note.</p>
    </div>
    """)