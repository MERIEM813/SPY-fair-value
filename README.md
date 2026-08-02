# Market Making Engine

A small model of how a market maker manages risk in real time on an ETF:
reconstruct fair value from the real underlying basket, quote a spread that
reacts to volatility, then skew that quote based on current inventory.

The goal isn't "an ETF fair value calculator" -- it's showing the reasoning
a trader actually uses: what's this worth right now, how much am I exposed
if I quote here, and which way should I lean given what I'm already holding.

## Architecture

```
fair_value.py   -> reconstructs SPY fair value from real SSGA holdings
quote_engine.py -> turns fair value into a bid/ask, spread widens with vol
inventory.py    -> skews that bid/ask based on current position
main.py         -> wires the three together, single data fetch
pnl.py          -> decomposes simulated PnL into spread pnl vs inventory pnl
```

Each module also runs standalone (`python3 fair_value.py`, etc.) for testing
in isolation -- `main.py` is the version you'd actually use, since it fetches
holdings + prices once and threads the same data through every step instead
of re-fetching per module.

### fair_value.py
Pulls SPY's real daily holdings file from State Street (503 tickers, not a
hand-picked top-N basket), reconstructs a weighted basket, and compares it
to the actual ETF price. Uses returns-based reconstruction (not rebased
price levels) to avoid cumulative drift over the window.

### quote_engine.py
Half-spread = a fixed floor + a term proportional to realized volatility
(rolling std of returns, annualized). Wider quotes when the market is
choppy, tighter when it's calm -- the spread reflects the risk of holding
the ETF between hedges, not an arbitrary constant.

### inventory.py
Simplified Avellaneda-Stoikov: skews the quote's center (not its width)
based on normalized position size and vol. Long position -> reservation
price shifts down (encourage selling); short -> shifts up. No terminal
horizon term, since this models a running market maker, not a single
session with a fixed end time.

### pnl.py
Decomposes PnL into two pieces a market maker has to track separately:
spread PnL (captured by buying below fair value / selling above it on
fills) and inventory PnL (mark-to-market gain/loss from holding a position
while fair value moves). Since there's no real order flow available, fills
are simulated with an independent per-side probability each day -- a toy
fill model, not a queue/order-book simulation. The point isn't the fill
model's realism, it's showing the decomposition itself: spread PnL is
structurally positive by construction, while inventory PnL can go either
way depending on market direction while a position is held.

## Known limitations (documented on purpose, not hidden)

- **Static weight snapshot.** SSGA's file gives today's weights, applied
  across the whole lookback window. SPY is cap-weighted, so real weights
  drift daily with price moves, not just at official rebalances -- this
  creates a systematic (not random) tracking deviation that grows with
  window length. Confirmed empirically: deviation grows from ~-56bps to
  ~-145bps over a 3-week window. This is why the window is kept to 1
  month rather than longer.
- **Spread and skew calibration are simplified heuristics** (linear in
  vol / normalized position), not fit to real order book or fill data.
  Good enough to show the right shape of behavior, not a production
  calibration.
- A couple of tickers (e.g. share classes like BRK.B) need a dot-to-hyphen
  mapping to match Yahoo Finance's ticker convention -- handled, but a
  reminder that "real data" always has small format mismatches to clean up.

## Running it

```bash
pip install -r requirements.txt
python3 main.py
```

## Roadmap (v2, not yet built)

- **volatility.py** -- a proper regime classifier (e.g. realized-vol
  percentile or VIX-based) to backtest how quotes/skew behave in calm vs
  stressed markets, rather than reacting to a single rolling-window number.
- **Dynamic historical weights** instead of one static snapshot, to remove
  the tracking-deviation bias documented above.
- **Real fill model** for pnl.py -- currently a random per-side probability
  per day, not a queue/order-book simulation.
