"""
inventory.py

Skews the quotes from quote_engine.py based on current position. Long ->
push both bid and ask down (get out of the position by encouraging sells).
Short -> push both up. Simplified Avellaneda-Stoikov: skew (in bps) scales
with position normalized to a reference size (MAX_POSITION) and with
annualized vol in percentage points -- no terminal horizon term since this
is a running MM, not a single session with a fixed end time.

Spread width itself is untouched here -- that's quote_engine's job. This
file only moves the center (bid+ask)/2 away from fair value.
"""

import pandas as pd

MAX_POSITION = 100    # position size treated as "full size" for normalizing skew
RISK_AVERSION = 1.0   # gamma: skew in bps at full position and 1% annualized vol


def reservation_price(fair_value, position, vol, risk_aversion=RISK_AVERSION, max_position=MAX_POSITION):
    norm_pos = position / max_position
    skew_bps = risk_aversion * norm_pos * (vol * 100)  # vol*100 = vol in % points
    skew = fair_value * skew_bps / 10000
    return fair_value - skew


def skewed_quotes(quotes, position, risk_aversion=RISK_AVERSION, max_position=MAX_POSITION):
    # quotes: output of quote_engine.generate_quotes (needs fair_value, vol, bid, ask)
    r = reservation_price(quotes["fair_value"], position, quotes["vol"], risk_aversion, max_position)
    half = (quotes["ask"] - quotes["bid"]) / 2

    out = quotes.copy()
    out["position"] = position
    out["reservation_price"] = r
    out["bid"] = r - half
    out["ask"] = r + half
    out["skew_bps"] = (r - quotes["fair_value"]) / quotes["fair_value"] * 10000
    return out


def run(position=50):
    from quote_engine import run as qe_run
    q = qe_run()
    return skewed_quotes(q, position).dropna()


if __name__ == "__main__":
    for pos in [-100, 0, 100]:
        df = run(position=pos)
        print(f"\nposition = {pos}")
        print(df[["fair_value", "reservation_price", "bid", "ask", "skew_bps"]].tail(5))
