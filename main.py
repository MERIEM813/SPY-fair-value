"""
main.py

Single entry point for the full pipeline: fair value -> quotes -> inventory
skew. Wired this way instead of calling each module's own run() separately,
because those each re-fetch SSGA holdings + yfinance prices from scratch --
fine for testing one module in isolation, wasteful (and slow) for a full
pipeline run where the underlying data doesn't change between steps.
"""

import fair_value
import quote_engine
import inventory

POSITIONS = [-100, 0, 100]  # inventory scenarios to show skew across


def run():
    fv_df = fair_value.run()
    fv = fv_df["fair_value_idx"]

    quotes = quote_engine.generate_quotes(fv).dropna()

    scenarios = {pos: inventory.skewed_quotes(quotes, pos).dropna() for pos in POSITIONS}
    return fv_df, quotes, scenarios


if __name__ == "__main__":
    fv_df, quotes, scenarios = run()

    print("=== fair value / tracking deviation ===")
    print(fv_df.tail(10))

    print("\n=== quotes (spread widens with realized vol) ===")
    print(quotes.tail(10))

    for pos, df in scenarios.items():
        print(f"\n=== inventory skew, position = {pos} ===")
        print(df[["fair_value", "reservation_price", "bid", "ask", "skew_bps"]].tail(5))
