"""
pnl.py

Decomposes market-making PnL into the two pieces that have to be tracked
separately:
  - spread pnl: captured on fills, buying below fair value / selling above it
  - inventory pnl: mark-to-market gain/loss from holding a position while
    fair value moves

We don't have real order flow, so fills are simulated: each day, the bid
and ask each have an independent chance of being hit (FILL_PROB). This is
a toy fill model, not a queue/order-book simulation -- good enough to show
the pnl decomposition itself, which is the actual point.
"""

import numpy as np
import pandas as pd

FILL_PROB = 0.5   # chance each side (bid/ask) gets hit on a given day
FILL_SIZE = 1     # units per fill
SEED = 42         # fixed seed so results are reproducible run to run


def simulate_fills(quotes, fill_prob=FILL_PROB, size=FILL_SIZE, seed=SEED):
    rng = np.random.default_rng(seed)
    position = 0
    rows = []

    for date, row in quotes.iterrows():
        spread_pnl = 0.0

        if rng.random() < fill_prob:   # someone sells to us at our bid
            position += size
            spread_pnl += size * (row["fair_value"] - row["bid"])

        if rng.random() < fill_prob:   # someone buys from us at our ask
            position -= size
            spread_pnl += size * (row["ask"] - row["fair_value"])

        rows.append({
            "date": date,
            "fair_value": row["fair_value"],
            "position": position,
            "spread_pnl": spread_pnl,
        })

    return pd.DataFrame(rows).set_index("date")


def compute_inventory_pnl(sim):
    # pnl from t-1 to t = position held over that interval * fair value change
    fv_change = sim["fair_value"].diff()
    return sim["position"].shift(1).fillna(0) * fv_change


def run():
    from main import run as main_run
    _, quotes, _ = main_run()

    sim = simulate_fills(quotes)
    sim["inventory_pnl"] = compute_inventory_pnl(sim).fillna(0)
    sim["total_pnl"] = sim["spread_pnl"] + sim["inventory_pnl"]

    sim["cum_spread_pnl"] = sim["spread_pnl"].cumsum()
    sim["cum_inventory_pnl"] = sim["inventory_pnl"].cumsum()
    sim["cum_total_pnl"] = sim["total_pnl"].cumsum()
    return sim


if __name__ == "__main__":
    sim = run()
    print(sim)

    print("\nsummary:")
    print(f"total spread pnl:    {sim['cum_spread_pnl'].iloc[-1]:.4f}")
    print(f"total inventory pnl: {sim['cum_inventory_pnl'].iloc[-1]:.4f}")
    print(f"total pnl:           {sim['cum_total_pnl'].iloc[-1]:.4f}")
