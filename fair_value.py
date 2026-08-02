
import io
import requests
import yfinance as yf
import pandas as pd
import numpy as np

SPY_HOLDINGS_URL = "https://www.ssga.com/us/en/institutional/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx"
TICKER = "SPY"


def fetch_spy_holdings():
    resp = requests.get(SPY_HOLDINGS_URL, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    raw = pd.read_excel(io.BytesIO(resp.content), header=None)

    # the file has a few metadata/title rows before the real table starts --
    # find the row that actually contains "Ticker" and use it as the header
    header_row = raw[raw.apply(lambda r: r.astype(str).str.strip().eq("Ticker").any(), axis=1)].index[0]
    df = pd.read_excel(io.BytesIO(resp.content), header=header_row)
    df = df.rename(columns=lambda c: str(c).strip())

    df = df.dropna(subset=["Ticker", "Weight"])
    df = df[df["Ticker"].astype(str).str.match(r"^[A-Z.]+$")]  # drop cash lines, footnotes
    df = df[~df["Ticker"].isin(["CASH", "USD", "NA"])]
    df["Weight"] = pd.to_numeric(df["Weight"], errors="coerce")
    df = df.dropna(subset=["Weight"])

    weights = dict(zip(df["Ticker"], df["Weight"] / 100))
    # yfinance/Yahoo use hyphens for share classes (BRK-B), SSGA file uses dots (BRK.B)
    weights = {t.replace(".", "-"): w for t, w in weights.items()}
    return weights


def fetch_prices(tickers, period="1mo", interval="1d"):
    data = yf.download(tickers, period=period, interval=interval, progress=False)["Close"]
    data = data.dropna(axis=1, how="all")  # drop tickers with no data at all first
    return data.dropna()


def reconstruct_fair_value(holdings_prices, weights):
    # returns-based reconstruction instead of rebased levels: avoids the
    # cumulative drift you get from rebasing to day-1 over a long window
    w = pd.Series(weights)
    w = w / w.sum()

    holdings_ret = holdings_prices.pct_change().dropna()
    basket_ret = (holdings_ret * w).sum(axis=1)

    # turn the daily basket return back into an index level, rebased at 100
    fair_value = 100 * (1 + basket_ret).cumprod()
    return fair_value


def compute_tracking_deviation(etf_price, fair_value):
    # weights are today's snapshot, not the true historical weights each day,
    # and a few tickers get dropped if yfinance has no clean data for them --
    # so this is still an approximation of tracking deviation, just close to
    # the real replication basket instead of a hand-picked top-N guess.
    etf_ret = etf_price.pct_change().dropna()
    etf_idx = 100 * (1 + etf_ret).cumprod()
    etf_idx = etf_idx.reindex(fair_value.index)

    spread_bps = (etf_idx - fair_value) / fair_value * 10000
    return spread_bps


def run():
    weights = fetch_spy_holdings()
    print(f"pulled {len(weights)} holdings from SSGA daily file")

    tickers = list(weights.keys()) + [TICKER]
    prices = fetch_prices(tickers)

    available = [t for t in weights if t in prices.columns]
    missing = [t for t in weights if t not in prices.columns]
    coverage = sum(weights[t] for t in available)
    print(f"matched {len(available)}/{len(weights)} tickers, {coverage*100:.1f}% of basket weight")
    if missing:
        print(f"missing tickers (dropped): {missing}")

    weights = {t: weights[t] for t in available}

    holdings_prices = prices[available]
    etf_price = prices[TICKER]

    fv = reconstruct_fair_value(holdings_prices, weights)
    spread = compute_tracking_deviation(etf_price, fv)

    out = pd.DataFrame({
        "etf_price": etf_price,
        "fair_value_idx": fv,
        "tracking_deviation_bps": spread,
    })
    return out


if __name__ == "__main__":
    df = run()
    print(df.tail(15))
    print("\nstats:")
    print(df["tracking_deviation_bps"].describe())
    print("\nNote: SPY is cap-weighted, so real weights drift every day with price")
    print("moves, not just at official rebalance dates. This model applies one static")
    print("weight snapshot across the whole window, which understates early-period")
    print("winners and creates a systematic (not random) deviation that grows with")
    print("window length -- this is why the window is kept short (1mo).")
