"""
storage.py
----------
Lightweight persistence for the "did I call it right?" feature: saves an
analysis (ticker, verdict, price at save-time) and later compares it
against the current price.

Uses SQLite (a single local file, no server/setup needed) — good enough
for an early-stage tool with no real user accounts yet. There's no login;
people identify themselves with a name/email they type in, purely as a
label to filter "their" saved analyses. This is NOT authentication — treat
it as a nickname, not a security boundary.

CAVEAT for cloud deployment: if you deploy this to a host with an
ephemeral filesystem (e.g. some free tiers reset storage on redeploy),
saved analyses won't persist across deploys. Fine for local use and
demos; worth a real database if this gets real users.
"""

import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "analyses.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_label TEXT NOT NULL,
            ticker TEXT NOT NULL,
            exchange TEXT NOT NULL,
            company_name TEXT,
            verdict_label TEXT,
            verdict_score INTEGER,
            price_at_save REAL,
            saved_at TEXT,
            ratio_snapshot TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_analysis(user_label, ticker, exchange, company_name, verdict, price_at_save, ratio_series):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO saved_analyses
           (user_label, ticker, exchange, company_name, verdict_label, verdict_score,
            price_at_save, saved_at, ratio_snapshot)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_label.strip().lower(),
            ticker.upper(),
            exchange,
            company_name,
            verdict["label"],
            verdict["score"],
            price_at_save,
            datetime.now(timezone.utc).isoformat(),
            json.dumps(ratio_series),
        ),
    )
    conn.commit()
    conn.close()


def list_analyses(user_label):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM saved_analyses WHERE user_label = ? ORDER BY saved_at DESC",
        (user_label.strip().lower(),),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def delete_analysis(analysis_id):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM saved_analyses WHERE id = ?", (analysis_id,))
    conn.commit()
    conn.close()


def get_current_price(ticker, exchange):
    """
    Fetch the latest closing price for a ticker. Works for US, NSE, and
    BSE tickers via yfinance (yfinance covers US stocks too, so we don't
    need a separate price source for the SEC path).
    """
    import yfinance as yf

    full_ticker = ticker.upper().strip()
    if exchange == "NSE" and not full_ticker.endswith(".NS"):
        full_ticker += ".NS"
    elif exchange == "BSE" and not full_ticker.endswith(".BO"):
        full_ticker += ".BO"

    hist = yf.Ticker(full_ticker).history(period="5d")
    if hist.empty:
        return None
    return float(hist["Close"].iloc[-1])
