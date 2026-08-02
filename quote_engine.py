"""
quote_engine.py

Takes the fair value series from fair_value.py and turns it into a bid/ask.
Half-spread = a fixed floor (covers fixed costs, adverse selection baseline)
+ a term that scales with realized vol -- wider quotes when the market is
choppy, tighter when it's calm. This is deliberately simple (no order book,
no queue position) -- it's the spread-setting layer, inventory skew comes
next in inventory.py.
"""

import numpy as np
import pandas as pd

BASE_SPREAD_BPS = 2      # floor half-spread even at zero vol
VOL_MULT = 1.0           # extra half-spread bps per 1 point of annualized vol (%)
VOL_WINDOW = 5           # rolling window (days) -- kept short since fair_value.py
                         # only produces ~20 usable rows on a 1mo lookback
ANNUALIZATION = np.sqrt(252)


def realized_vol(fair_value, window=VOL_WINDOW):
    ret = fair_value.pct_change()
    return ret.rolling(window).std() * ANNUALIZATION


def generate_quotes(fair_value, window=VOL_WINDOW, base_bps=BASE_SPREAD_BPS, vol_mult=VOL_MULT):
    vol = realized_vol(fair_value, window)
    half_bps = base_bps + vol_mult * (vol * 100)  # vol*100 = annualized vol in % points
    half = fair_value * half_bps / 10000

    return pd.DataFrame({
        "fair_value": fair_value,
        "vol": vol,
        "half_spread_bps": half_bps,
        "bid": fair_value - half,
        "ask": fair_value + half,
    })


def run():
    from fair_value import run as fv_run
    fv = fv_run()["fair_value_idx"]
    return generate_quotes(fv).dropna()


if __name__ == "__main__":
    q = run()
    print(q.tail(15))
    print("\nstats:")
    print(q["half_spread_bps"].describe())
