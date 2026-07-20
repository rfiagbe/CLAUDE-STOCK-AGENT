"""Screens the S&P 500 for momentum/trend candidates and ranks them."""

import io
import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# Liquid large-cap fallback if the Wikipedia fetch fails.
FALLBACK_TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "BRK-B",
    "LLY", "JPM", "V", "UNH", "XOM", "MA", "COST", "HD", "PG", "JNJ", "ABBV",
    "NFLX", "CRM", "BAC", "ORCL", "MRK", "KO", "AMD", "CVX", "PEP", "ADBE",
    "TMO", "WMT", "LIN", "MCD", "CSCO", "ACN", "ABT", "GE", "IBM", "QCOM",
    "CAT", "TXN", "INTU", "AMAT", "DIS", "VZ", "PFE", "NOW", "UBER", "AMGN",
    "PM", "GS", "ISRG", "NEE", "RTX", "SPGI", "HON", "BKNG", "UNP", "LOW",
    "ETN", "AXP", "T", "SYK", "MU", "BLK", "TJX", "PANW", "LRCX", "ADI",
    "BSX", "VRTX", "C", "MDT", "SCHW", "PGR", "KLAC", "REGN", "DE", "MMC",
    "CB", "FI", "ANET", "SO", "PLD", "MO", "CI", "DUK", "SBUX", "GILD",
    "ZTS", "CME", "SHW", "EQIX", "ICE", "CDNS", "SNPS", "USB", "CL", "WM",
]


def get_universe() -> list[str]:
    """S&P 500 tickers from Wikipedia, falling back to a static list."""
    try:
        import requests

        resp = requests.get(SP500_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
        tickers = tables[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        if len(tickers) > 400:
            log.info("Universe: %d S&P 500 tickers from Wikipedia", len(tickers))
            return tickers
    except Exception as exc:
        log.warning("Could not fetch S&P 500 list (%s); using fallback list", exc)
    return FALLBACK_TICKERS


def _rsi(close: pd.Series, window: int = 14) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, min_periods=window).mean()
    rs = gain / loss
    return float((100 - 100 / (1 + rs)).iloc[-1])


def _score_ticker(close: pd.Series, volume: pd.Series) -> dict | None:
    """Compute filter/score metrics for one ticker. None = filtered out."""
    close = close.dropna()
    if len(close) < 210:  # need ~1y of bars for the 200-day average
        return None

    price = float(close.iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1])
    avg_dollar_vol = float((close * volume).rolling(63).mean().iloc[-1])

    # Liquidity and uptrend filters
    if price < 5 or avg_dollar_vol < 20e6:
        return None
    if not (price > sma20 and price > sma50 and sma50 > sma200):
        return None

    rsi = _rsi(close)
    if rsi >= 75:  # skip the most overheated names
        return None

    ret_1m = price / float(close.iloc[-21]) - 1
    ret_3m = price / float(close.iloc[-63]) - 1
    ret_6m = price / float(close.iloc[-126]) - 1
    high_52w = float(close.iloc[-252:].max())
    pct_from_high = price / high_52w - 1  # negative or zero
    vol_surge = float(volume.iloc[-5:].mean() / volume.rolling(63).mean().iloc[-1])
    low_20d = float(close.iloc[-20:].min())

    # Momentum blend, rewarding names holding near their highs
    score = (
        0.35 * ret_3m
        + 0.25 * ret_1m
        + 0.20 * ret_6m
        + 0.20 * max(pct_from_high, -0.25)  # cap the penalty
    )

    return {
        "price": price,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_6m": ret_6m,
        "rsi": rsi,
        "sma50": sma50,
        "pct_from_high": pct_from_high,
        "vol_surge": vol_surge,
        "low_20d": low_20d,
        "avg_dollar_vol": avg_dollar_vol,
        "score": score,
    }


def run_screen(top_n: int = 5) -> pd.DataFrame:
    """Download 1y of daily bars for the universe and return the top-ranked names."""
    tickers = get_universe()
    log.info("Downloading price history for %d tickers...", len(tickers))
    data = yf.download(
        tickers, period="1y", interval="1d", group_by="ticker",
        auto_adjust=True, threads=True, progress=False,
    )

    rows = {}
    for t in tickers:
        try:
            df = data[t] if isinstance(data.columns, pd.MultiIndex) else data
            metrics = _score_ticker(df["Close"], df["Volume"])
            if metrics:
                rows[t] = metrics
        except (KeyError, IndexError, ValueError):
            continue

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame.from_dict(rows, orient="index")
    result.index.name = "ticker"
    result = result.sort_values("score", ascending=False).head(top_n)

    # Attach company names for the email (best effort)
    names = {}
    for t in result.index:
        try:
            names[t] = yf.Ticker(t).info.get("shortName", t)
        except Exception:
            names[t] = t
    result["name"] = pd.Series(names)
    log.info("Screen passed %d names; returning top %d", len(rows), len(result))
    return result
