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
import json

from edgar_client import get_cik_for_ticker, get_company_facts, extract_annual_series
from ratios import REQUIRED_TAGS, compute_ratios, year_over_year_changes, flag_anomalies

st.set_page_config(
    page_title="Filytic",
    page_icon="◉",
    layout="wide",
)

# ---------------------------------------------------------------------------
# INTRO LOADER + ONE-TIME GUIDED WALKTHROUGH
# Both are pure client-side (HTML/CSS/JS) — the walkthrough's dismissal is
# stored in the browser's localStorage, so it genuinely only shows once per
# visitor, ever, without needing a Streamlit rerun to remember that.
# ---------------------------------------------------------------------------
st.html("""
<style>
#intro-loader {
    position: fixed; inset: 0; z-index: 9999;
    background: #080808; display:flex; align-items:center; justify-content:center;
    flex-direction: column; gap: 1rem;
    animation: loader-fade 0.5s ease 1.05s forwards;
}
#intro-loader.hidden { pointer-events: none; }
@keyframes loader-fade { to { opacity: 0; visibility: hidden; } }
#intro-loader-pct {
    font-family:'Anton',Impact,sans-serif; font-size: 4rem; color:#f2f1e8; letter-spacing:.02em;
}
#intro-loader-label {
    font-family:'DM Mono',monospace; font-size:.62rem; text-transform:uppercase;
    letter-spacing:.15em; color:#6f6b64;
}

#guide-overlay {
    position: fixed; inset: 0; z-index: 9998;
    background: rgba(8,8,8,0.88); display:none;
    align-items:center; justify-content:center; padding: 2rem;
}
#guide-overlay.visible { display:flex; }
#guide-card {
    background:#141416; border:1px solid #302e2d; border-radius:20px;
    max-width: 480px; width:100%; padding: 2rem 2.2rem;
    font-family:'Inter',sans-serif; color:#f2f1e8;
    animation: verdict-pop .4s cubic-bezier(.2,.8,.2,1) both;
}
#guide-eyebrow {
    font-family:'DM Mono',monospace; font-size:.6rem; text-transform:uppercase;
    letter-spacing:.12em; color:#ff5a1f; margin-bottom:.6rem;
}
#guide-title { font-family:'Anton',Impact,sans-serif; font-size:1.7rem; text-transform:uppercase; margin-bottom:.8rem; line-height:1.05; }
#guide-body { font-size:.92rem; line-height:1.6; color:#bdb9b2; margin-bottom:1.4rem; min-height:60px; }
#guide-footer { display:flex; align-items:center; justify-content:space-between; }
#guide-dots { display:flex; gap:.4rem; }
.guide-dot { width:6px; height:6px; border-radius:50%; background:#3a3734; transition: background .2s ease; }
.guide-dot.active { background:#ff5a1f; }
.guide-btn {
    font-family:'DM Mono',monospace; font-size:.66rem; text-transform:uppercase; letter-spacing:.06em;
    background:transparent; border:1px solid #4a403a; color:#f2f1e8; border-radius:999px;
    padding:.5rem 1.1rem; cursor:pointer; transition:.2s ease;
}
.guide-btn:hover { background:#ff5a1f; border-color:#ff5a1f; color:#111; }
.guide-btn.skip { border:none; color:#8c8780; padding-left:0; }
.guide-btn.skip:hover { background:transparent; color:#f2f1e8; }
</style>

<div id="intro-loader">
    <div id="intro-loader-pct">0%</div>
    <div id="intro-loader-label">Filytic</div>
</div>

<div id="guide-overlay">
    <div id="guide-card">
        <div id="guide-eyebrow">How this works</div>
        <div id="guide-title">Step <span id="guide-step-num">1</span> of 5</div>
        <div id="guide-body"></div>
        <div id="guide-footer">
            <div id="guide-dots"></div>
            <div style="display:flex; gap:.6rem; align-items:center;">
                <button class="guide-btn skip" onclick="filyticSkipGuide()">Skip</button>
                <button class="guide-btn" id="guide-next-btn" onclick="filyticNextGuide()">Next</button>
            </div>
        </div>
    </div>
</div>

<script>
(function() {
    // --- Intro loader: purely decorative, plays once per page load ---
    const pctEl = document.getElementById('intro-loader-pct');
    const loaderEl = document.getElementById('intro-loader');
    if (pctEl && loaderEl) {
        let pct = 0;
        const start = performance.now();
        const duration = 900;
        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            pct = Math.round(progress * 100);
            pctEl.textContent = pct + '%';
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
        setTimeout(function() { loaderEl.classList.add('hidden'); }, 1600);
    }

    // --- One-time guided walkthrough: dismissal persists via localStorage ---
    const STORAGE_KEY = 'filytic_guide_seen_v1';
    const steps = [
        "Pick an exchange (US via SEC, or NSE/BSE for Indian stocks) and type a ticker \u2014 the company's stock code, like AAPL or RELIANCE.",
        "Set the anomaly threshold if you want, then hit Analyze. This pulls the company's real financial filings and computes 10 standard ratios across every year on file.",
        "You'll get an overall verdict (Looks Healthy / Mixed Signals / Watch Closely), the ratio trends, and a plain-English note explaining what's worth digging into \u2014 no finance background assumed.",
        "Enter your name or email up top, then hit \"Save this analysis\" on anything you want to track \u2014 it records the verdict and the current price.",
        "Later, open \"My Analyses\" and hit \"Check thesis status\" \u2014 it re-checks the latest filing and tells you if your original read still holds, not just whether the price moved."
    ];
    let stepIndex = 0;

    window.filyticNextGuide = function() {
        stepIndex++;
        if (stepIndex >= steps.length) { window.filyticSkipGuide(); return; }
        renderStep();
    };
    window.filyticSkipGuide = function() {
        try { localStorage.setItem(STORAGE_KEY, '1'); } catch (e) {}
        const overlay = document.getElementById('guide-overlay');
        if (overlay) overlay.classList.remove('visible');
    };

    // Manual re-trigger (e.g. an "How does this work?" button elsewhere on
    // the page) — separate from the auto-show-on-first-visit logic below,
    // so returning visitors can still pull up the walkthrough on demand.
    window.filyticShowGuide = function() {
        stepIndex = 0;
        renderStep();
        const overlay = document.getElementById('guide-overlay');
        if (overlay) overlay.classList.add('visible');
    };

    function renderStep() {
        document.getElementById('guide-step-num').textContent = stepIndex + 1;
        document.getElementById('guide-body').textContent = steps[stepIndex];
        document.getElementById('guide-next-btn').textContent = (stepIndex === steps.length - 1) ? "Got it" : "Next";
        const dotsEl = document.getElementById('guide-dots');
        dotsEl.innerHTML = steps.map(function(_, i) {
            return '<div class="guide-dot' + (i === stepIndex ? ' active' : '') + '"></div>';
        }).join('');
    }

    let alreadySeen = false;
    try { alreadySeen = localStorage.getItem(STORAGE_KEY) === '1'; } catch (e) {}
    if (!alreadySeen) {
        renderStep();
        setTimeout(function() {
            const overlay = document.getElementById('guide-overlay');
            if (overlay) overlay.classList.add('visible');
        }, 1700);
    }
})();
</script>
""", unsafe_allow_javascript=True)

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
.brand { color: var(--paper) !important; font-weight:400; letter-spacing:.08em; }
.top-links { display:flex; gap:1.4rem; color:#78746e; }
.top-links a { color:#78746e !important; text-decoration:none; transition: color .2s ease; }
.top-links a:hover { color: var(--orange) !important; }

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
    position:relative; z-index:4; max-width:560px; margin:1.8rem auto 0;
    text-align:center; color:#78746e !important; font-size:.82rem; line-height:1.6;
}

.cta-row { position:relative; z-index:5; display:flex; justify-content:center; margin-top:1.6rem; }
.stButton>button {
    background:transparent !important; color:var(--paper) !important;
    border:1px solid #3a3734 !important; border-radius:999px !important;
    min-height:44px; padding:0 2.2rem !important; font-family:'DM Mono',monospace !important;
    text-transform:uppercase; letter-spacing:.05em; font-size:.68rem !important;
    transition:.2s ease;
}
.stButton>button:hover { background:var(--orange) !important; color:#080808 !important; border-color:var(--orange) !important; transform:translateY(-1px); }
.stButton>button p { color:inherit !important; }

.ticker-strip {
    border-top:1px solid #24211f; border-bottom:1px solid #24211f;
    overflow:hidden; white-space:nowrap; padding:.55rem 0;
    font-family:'DM Mono',monospace; font-size:.54rem; color:#5c5952;
    text-transform:uppercase; letter-spacing:.08em;
}
.ticker-track {
    display:inline-flex; animation: ticker-scroll 22s linear infinite;
}
.ticker-track span { margin-right:2.5rem; }
@keyframes ticker-scroll {
    from { transform: translateX(0); }
    to   { transform: translateX(-50%); }
}

.control-panel {
    background:transparent; border:none; border-top:1px solid #24211f; border-bottom:1px solid #24211f;
    padding:1.1rem 0; margin:1.4rem 0 1.6rem;
}
.control-label { font-family:'DM Mono'; text-transform:uppercase; font-size:.58rem; color:#6f6b64 !important; letter-spacing:.1em; margin-bottom:.5rem; }
.stTextInput input, .stNumberInput input {
    background:transparent !important; color:var(--paper) !important; border:none !important;
    border-bottom:1px solid #3a3734 !important; border-radius:0 !important; padding-left:0 !important;
}
.stTextInput input:focus { border-bottom-color: var(--orange) !important; box-shadow:none !important; }
.stSlider [data-baseweb="slider"] { padding-top:.25rem; }
.stSlider label, .stTextInput label { color:#6f6b64 !important; }

/* Dashboard elements — editorial, hairline-divided, minimal boxing.
   ONE accent color (orange) used only where something needs attention;
   everything else stays monochrome (off-white on near-black). */
.card {
    background: transparent; border: none; border-bottom: 1px solid #24211f;
    border-radius: 0; padding: 1.5rem 0; box-shadow: none; margin-bottom: 0;
    transition: padding-left .25s ease;
    animation: card-rise .5s ease both;
}
.card:hover { padding-left: .35rem; }
.card-boxed {
    /* Used sparingly, for things that genuinely benefit from visual separation
       (the guided overlay, error states) — not the default dashboard look. */
    background:#141416; border:1px solid #24211f; border-radius:16px; padding:1.35rem;
}
@keyframes card-rise {
    from { opacity:0; transform: translateY(10px); }
    to   { opacity:1; transform: translateY(0); }
}
@keyframes verdict-pop {
    0%   { opacity:0; transform: scale(.97); }
    100% { opacity:1; transform: scale(1); }
}
.verdict-reveal { animation: verdict-pop .6s cubic-bezier(.2,.8,.2,1) both; }

.verdict-label {
    font-family:'Anton',Impact,sans-serif; text-transform:uppercase;
    font-size: clamp(2.4rem, 5vw, 3.6rem); line-height:.95; letter-spacing:-.01em;
    color: var(--paper) !important; margin: .3rem 0 1rem;
}
.verdict-marker {
    display:inline-block; width:9px; height:9px; border-radius:50%;
    background: var(--orange); margin-right:.6rem; vertical-align:middle;
}
.verdict-marker.calm { background:#4a453e; }

/* Animated count-up numbers */
.count-up { display:inline-block; }

/* Animated sparkline draw-in */
.sparkline-path {
    stroke-dasharray: 600;
    stroke-dashoffset: 600;
    animation: draw-line 1.1s ease forwards;
}
@keyframes draw-line {
    to { stroke-dashoffset: 0; }
}
.sparkline-fill {
    opacity: 0;
    animation: fade-in-fill .8s ease .6s forwards;
}
@keyframes fade-in-fill {
    to { opacity: 1; }
}

.eyebrow { text-transform:uppercase; letter-spacing:.09em; font-family:'DM Mono',monospace;
    font-size:.58rem; font-weight:500; color:#8f8a83 !important; margin-bottom:.35rem; }
.headline { font-family:'Anton',Impact,sans-serif !important; font-size:2.5rem; line-height:.95; color:var(--orange) !important; text-transform:uppercase; letter-spacing:.01em; }
.big-stat { font-family:'Anton',Impact,sans-serif; font-size:2.4rem; color:var(--paper) !important; text-align:right; }
.ratio-card-number { font-family:'Anton',Impact,sans-serif; font-size:2rem; color:var(--paper) !important; }
.ratio-card-caption { font-family:'DM Mono',monospace; font-size:.58rem; color:#77736d !important; }
.yoy-badge { display:inline-flex; padding:.28rem .65rem; border:1px solid #4a403a; border-radius:999px; font-family:'DM Mono'; font-size:.58rem; color:var(--orange) !important; transition: border-color .2s ease, transform .2s ease; }
.yoy-badge:hover { border-color: var(--orange); transform: translateY(-1px); }
.yoy-badge.positive, .yoy-badge.negative { background:transparent; color:var(--orange) !important; }
.flag-row { display:flex; justify-content:space-between; padding:.72rem 0; border-bottom:1px solid #2b2928; transition: padding-left .2s ease, background .2s ease; }
.flag-row:hover { padding-left:.4rem; background: rgba(255,255,255,0.02); }
.flag-label { color:#bcb7af !important; font-size:.82rem; }
.flag-value { font-family:'DM Mono'; font-size:.76rem; }
.flag-value.positive, .flag-value.negative { color:var(--orange) !important; }
.narrative-box { background:#111113; border-left:2px solid var(--orange); padding:1.35rem 1.5rem; border-radius:0; line-height:1.75; color:#c1bcb4 !important; }
.streamlit-expanderHeader { background:transparent !important; border:none !important; border-top:1px solid #24211f !important; color:var(--paper) !important; border-radius:0 !important; }
[data-testid="stDataFrame"] { border-radius:10px; overflow:hidden; }

/* Mobile */
@media (max-width: 800px) {
    .main .block-container { padding: .8rem .8rem 3rem; }
    .hero { min-height:420px; padding:2rem .8rem; }
    .hero-title { width:94%; font-size:clamp(3.2rem,13vw,5rem); }
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
    <div class="brand">FILYTIC</div>
    <div class="top-links">
        <a href="?view=dashboard">/dashboard</a>
        <a href="?view=my_analyses">/my-analyses</a>
        <a href="?view=about">/about</a>
    </div>
  </div>
</div>
""")

if "view" not in st.session_state:
    st.session_state["view"] = "dashboard"

# The topbar links above navigate via the URL's ?view= query param (a real
# link, not a Streamlit widget — this is what lets a single set of nav
# links live inside the same minimal topbar instead of duplicating them as
# a separate row of boxed buttons). Read it once per run to sync state.
query_view = st.query_params.get("view")
if query_view in ("dashboard", "my_analyses", "about"):
    st.session_state["view"] = query_view

st.markdown("<div class='control-label'>Your name or email (to save analyses)</div>", unsafe_allow_html=True)
user_label = st.text_input("User label", placeholder="e.g. your.email@example.com", label_visibility="collapsed")

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
    <div>
      <div class="hero-title">
        <span class="line">For every filing,</span>
        <span class="line italic">and what it's not telling you.</span>
      </div>
      <div class="hero-sub">Real financial filings, reduced to the ratios and movements that matter — explained in plain English, not analyst jargon.</div>
      <div class="cta-row"><span style="font-family:'DM Mono';font-size:.58rem;color:#5c5952;letter-spacing:.1em;">↑ enter a ticker to begin</span></div>
    </div>
  </div>
  <div class="ticker-strip">
    <div class="ticker-track">
        <span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span>
        <span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span><span>IT ALL BEGINS WITH THE 10-K</span><span>•</span>
    </div>
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
    """Colored area sparkline (SVG) with a draw-in animation on load."""
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
        <polygon class="sparkline-fill" points="{area_points}" fill="{fill}" />
        <polyline class="sparkline-path" fill="none" stroke="{stroke}" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round" points="{line_points}" />
    </svg>"""


def yoy_badge(pct):
    cls = "positive" if pct >= 0 else "negative"
    return f"<span class='yoy-badge {cls}'>{pct:+.1f}% YoY</span>"


def count_up(value_display: str, target: float, duration_ms: int = 900, decimals: int = 0, prefix: str = "", suffix: str = "") -> str:
    """
    Renders a number that animates counting up from 0 to its final value
    on load, using a small self-contained inline script (safe inside
    st.html() — no cross-render state, just a one-time visual effect).
    Falls back to a plain static number if target isn't a real number.
    """
    import uuid
    if target is None:
        return value_display
    elem_id = f"countup_{uuid.uuid4().hex[:8]}"
    return f"""<span id="{elem_id}">{prefix}0{suffix}</span>
    <script>
        (function() {{
            const el = document.getElementById("{elem_id}");
            if (!el) return;
            const target = {target};
            const duration = {duration_ms};
            const decimals = {decimals};
            const start = performance.now();
            function tick(now) {{
                const progress = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = target * eased;
                el.textContent = "{prefix}" + current.toFixed(decimals) + "{suffix}";
                if (progress < 1) requestAnimationFrame(tick);
            }}
            requestAnimationFrame(tick);
        }})();
    </script>"""


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
            <div class="card-boxed" style="max-width:760px;margin:1.2rem auto 0;text-align:center;">
                <div class="verdict-label" style="font-size:1.6rem;"><span class="verdict-marker calm"></span>Nothing saved yet</div>
                <p style="margin:1rem 0 0; color:#a19c94;">Run an analysis on the Dashboard tab, then hit "Save this analysis"
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
                                <div class="verdict-label" style="font-size:1.4rem;">{row['company_name']}</div>
                                <p style="margin-top:0.5rem; color:#a19c94;">You flagged this: <strong style="color:var(--paper);">{row['verdict_label']}</strong></p>
                                <p style="margin-top:0.25rem; color:#a19c94;">{price_line}</p>
                            </div>
                        </div>
                    </div>
                    """)

                    thesis_key = f"thesis_result_{row['id']}"
                    if st.button("Check thesis status", key=f"thesis_btn_{row['id']}"):
                        from thesis import refetch_current_ratios, compare_thesis, STATUS_MESSAGES
                        with st.spinner("Re-checking the latest filing..."):
                            # JSON object keys are always strings, so the fiscal-year
                            # keys (e.g. 2024) come back as "2024" after this round-trip.
                            # Convert them back to int so they compare correctly against
                            # the freshly re-fetched data below (which has real int keys).
                            old_ratio_series = {
                                int(fy): ratios for fy, ratios in json.loads(row["ratio_snapshot"]).items()
                            }
                            new_ratio_series, new_flags = refetch_current_ratios(row["ticker"], row["exchange"])
                            if new_ratio_series is None:
                                st.session_state[thesis_key] = {"error": "Couldn't re-fetch data for this ticker right now."}
                            else:
                                st.session_state[thesis_key] = compare_thesis(
                                    old_ratio_series, row["verdict_label"], new_ratio_series, new_flags
                                )
                        st.rerun()

                    if thesis_key in st.session_state:
                        from thesis import STATUS_MESSAGES
                        result = st.session_state[thesis_key]
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            needs_attention = result["status"] in ("weakening", "holding_with_moves")
                            marker_cls = "" if needs_attention else "calm"
                            st.html(f"""
                            <div class="card-boxed" style="margin-top:0.75rem;">
                                <p style="margin:0;"><span class="verdict-marker {marker_cls}"></span><strong>{STATUS_MESSAGES[result['status']]}</strong></p>
                                {"<ul style='margin:0.6rem 0 0; padding-left:1.6rem; color:#a19c94;'>" + "".join(f"<li>{s}</li>" for s in result["shifts"]) + "</ul>" if result["shifts"] else ""}
                            </div>
                            """)
                with col_del:
                    if st.button("Delete", key=f"del_{row['id']}"):
                        delete_analysis(row["id"])
                        st.rerun()

elif st.session_state["view"] == "about":
    st.html("""
    <div class="editorial-shell" style="max-width:760px; margin:1.5rem auto; padding:2rem 2.2rem;">
        <div class="eyebrow">About this tool</div>
        <div class="verdict-label" style="font-size:2rem; margin-bottom:1.4rem;">
            <span class="verdict-marker calm"></span>How Filytic actually works
        </div>

        <p style="color:#a19c94; line-height:1.75; margin-bottom:1.6rem;">
            Filytic pulls a company's real financial filings, computes the ratios that
            matter, flags what moved sharply, and explains it in plain English &mdash;
            no finance background assumed. Here's what's actually happening under the hood.
        </p>

        <div class="card">
            <div class="eyebrow">SEC EDGAR (US stocks)</div>
            <p style="color:#a19c94; line-height:1.7; margin:0;">
                Every U.S. public company is legally required to file an annual report
                called a <strong style="color:var(--paper);">10-K</strong> with the SEC
                (the U.S. government agency that regulates the stock market). EDGAR is
                SEC's free, public database of every filing ever submitted &mdash; Filytic
                reads directly from it, with no API key required. The numbers you see
                come straight from the company's own audited filings, not an estimate.
            </p>
        </div>

        <div class="card">
            <div class="eyebrow">NSE &amp; BSE (Indian stocks)</div>
            <p style="color:#a19c94; line-height:1.7; margin:0;">
                India's two major stock exchanges &mdash; the National Stock Exchange and
                the Bombay Stock Exchange. There's no free equivalent of SEC's EDGAR
                for Indian filings, so this data comes from Yahoo Finance instead. It's
                generally reliable for large, well-covered companies, but less
                standardized than SEC data &mdash; treat it accordingly for smaller or
                less-covered tickers.
            </p>
        </div>

        <div class="card">
            <div class="eyebrow">What "ticker" and other terms mean</div>
            <p style="color:#a19c94; line-height:1.7; margin:0;">
                A <strong style="color:var(--paper);">ticker</strong> is a company's short
                stock-market code (e.g. AAPL for Apple). A
                <strong style="color:var(--paper);">fiscal year</strong> is a company's own
                12-month accounting year &mdash; it doesn't have to match the calendar year.
                The <strong style="color:var(--paper);">verdict</strong> (Looks Healthy /
                Mixed Signals / Watch Closely) is a single simplified read combining
                liquidity, leverage, and profitability &mdash; a starting point for digging
                deeper, not a final answer.
            </p>
        </div>

        <div class="card" style="text-align:center;">
            <p style="color:#a19c94; margin:0 0 .9rem;">Want to see the full walkthrough again?</p>
            <button class="guide-btn" style="padding:.6rem 1.6rem;" onclick="if(window.filyticShowGuide){window.filyticShowGuide();}">Show me how this works</button>
        </div>

        <p style="color:#5c5952; font-size:.75rem; margin-top:1.6rem;">
            &#9888;&#65039; For informational and educational purposes only. This is not
            investment advice. Always verify against original filings before making
            any decisions.
        </p>
    </div>
    """, unsafe_allow_javascript=True)

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

        # --- Header card ---
        margin_values = [ratio_series[y]["net_margin"] for y in years]
        first_val = next((v for v in margin_values if v is not None), None)
        last_val = margin_values[-1]
        overall_pct = None
        if first_val and last_val is not None and first_val != 0:
            overall_pct = ((last_val - first_val) / abs(first_val)) * 100

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
                            <div class="big-stat">{count_up("", total_flags, decimals=0)}</div>
                        </div>
                        {yoy_badge(overall_pct) if overall_pct is not None else ""}
                    </div>
                </div>
            </div>
            """, unsafe_allow_javascript=True)

        # --- Verdict card + save button ---
        from verdict import compute_verdict
        verdict = compute_verdict(ratio_series, flags)
        marker_class = "calm" if verdict["label"] == "Looks Healthy" else ""

        v_l, v_r = st.columns([3, 1.4])
        with v_l:
            st.html(f"""
            <div class="card verdict-reveal">
                <div class="eyebrow">Overall verdict</div>
                <div class="verdict-label"><span class="verdict-marker {marker_class}"></span>{verdict['label']}</div>
                <ul style="margin:0 0 0 1.4rem; padding:0; color:#a19c94; line-height:1.7;">
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

        # --- Three ratio cards with monochrome sparklines (one accent system) ---
        stat_defs = [
            ("Net Margin", "net_margin"),
            ("ROE", "roe"),
            ("Current Ratio", "current_ratio"),
        ]
        c1, c2, c3 = st.columns(3)
        for col, (label, key) in zip([c1, c2, c3], stat_defs):
            series_vals = [ratio_series[y][key] for y in years]
            latest_val = ratio_series[latest][key]
            number_display = count_up("", latest_val, decimals=3) if latest_val is not None else "—"
            with col:
                st.html(f"""
                <div class="card">
                    <div class="eyebrow">{label}</div>
                    {render_area_sparkline(series_vals, "#f2f1e8", "rgba(242,241,232,0.08)")}
                    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:0.5rem;">
                        <span class="ratio-card-number">{number_display}</span>
                        <span class="ratio-card-caption">As of FY{latest}</span>
                    </div>
                </div>
                """, unsafe_allow_javascript=True)

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
    <div class="card-boxed" style="max-width:760px;margin:1.2rem auto 0;text-align:center;">
        <div class="eyebrow">How it works</div>
        <div class="headline" style="font-size:2rem;">One ticker. Every important movement.</div>
        <p style="margin:1rem 0 0; color:#a19c94;">SEC EDGAR data → annual ratios → year-over-year changes → anomaly flags → plain-English analyst note.</p>
    </div>
    """)