"""Records daily picks to picks_history.csv and fills in closing prices at EOD."""

import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent / "picks_history.csv"
BENCH_PATH = Path(__file__).parent / "benchmark_history.csv"
COLUMNS = ["date", "rank", "ticker", "name", "pick_price",
           "close_price", "day_change_pct", "updated_at"]


def _load() -> pd.DataFrame:
    if CSV_PATH.exists():
        hist = pd.read_csv(CSV_PATH, dtype={"date": str, "updated_at": str})
        hist["updated_at"] = hist["updated_at"].astype("string")
        return hist
    return pd.DataFrame(columns=COLUMNS)


def record_picks(picks: pd.DataFrame) -> None:
    """Append today's picks to the history CSV (replacing any existing rows for today)."""
    today = date.today().isoformat()
    hist = _load()
    hist = hist[hist["date"] != today]  # idempotent: re-running replaces today

    new_rows = pd.DataFrame({
        "date": today,
        "rank": range(1, len(picks) + 1),
        "ticker": picks.index,
        "name": picks["name"].values,
        "pick_price": picks["price"].round(2).values,
        "close_price": pd.NA,
        "day_change_pct": pd.NA,
        "updated_at": pd.NA,
    })
    hist = pd.concat([hist, new_rows], ignore_index=True)
    hist.to_csv(CSV_PATH, index=False)
    log.info("Recorded %d picks for %s in %s", len(new_rows), today, CSV_PATH.name)


def update_closes() -> pd.DataFrame:
    """Fill in closing prices for rows that don't have one yet.

    Returns the rows updated in this run (empty DataFrame if none).
    """
    hist = _load()
    if hist.empty:
        log.info("No history file / no rows to update.")
        return pd.DataFrame()

    pending = hist["close_price"].isna()
    if not pending.any():
        log.info("All rows already have closing prices.")
        return pd.DataFrame()

    tickers = sorted(hist.loc[pending, "ticker"].unique())
    log.info("Fetching closes for %d tickers...", len(tickers))
    data = yf.download(tickers, period="1mo", interval="1d", group_by="ticker",
                       auto_adjust=True, threads=True, progress=False)

    updated_idx = []
    for idx in hist.index[pending]:
        row = hist.loc[idx]
        try:
            closes = (data[row["ticker"]]["Close"]
                      if isinstance(data.columns, pd.MultiIndex) else data["Close"]).dropna()
        except KeyError:
            continue
        closes.index = pd.to_datetime(closes.index).date
        row_date = date.fromisoformat(row["date"])

        if row_date in closes.index:
            close = float(closes[row_date])
        elif len(closes) > 0 and (date.today() - row_date) <= timedelta(days=5):
            # No bar on that exact date (weekend/holiday run): use latest close
            close = float(closes.iloc[-1])
            log.info("%s %s: no bar on that date, using latest close",
                     row["ticker"], row["date"])
        else:
            continue

        hist.loc[idx, "close_price"] = round(close, 2)
        hist.loc[idx, "day_change_pct"] = round(
            (close / float(row["pick_price"]) - 1) * 100, 2)
        hist.loc[idx, "updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        updated_idx.append(idx)

    if updated_idx:
        hist.to_csv(CSV_PATH, index=False)
        log.info("Updated %d rows with closing prices.", len(updated_idx))
    return hist.loc[updated_idx]


def update_benchmark() -> None:
    """Record SPY's close and day change for every pick date not yet covered.

    Gives the dashboard an S&P 500 baseline to compare the agent against.
    """
    hist = _load()
    if hist.empty:
        return
    bench = (pd.read_csv(BENCH_PATH, dtype={"date": str}) if BENCH_PATH.exists()
             else pd.DataFrame(columns=["date", "spy_close", "spy_change_pct"]))
    missing = sorted(set(hist["date"]) - set(bench["date"]))
    if not missing:
        return

    spy = yf.download("SPY", period="3mo", interval="1d",
                      auto_adjust=True, progress=False)["Close"].dropna()
    if isinstance(spy, pd.DataFrame):  # yfinance may return a 1-col frame
        spy = spy.iloc[:, 0]
    spy.index = pd.to_datetime(spy.index).date

    new_rows = []
    for d in missing:
        row_date = date.fromisoformat(d)
        if row_date in spy.index:
            pos = list(spy.index).index(row_date)
            close = float(spy.iloc[pos])
            chg = (close / float(spy.iloc[pos - 1]) - 1) * 100 if pos > 0 else 0.0
        elif len(spy) > 0 and (date.today() - row_date) <= timedelta(days=5):
            # Weekend/holiday run: mirror the picks' fallback (latest close, flat day)
            close, chg = float(spy.iloc[-1]), 0.0
        else:
            continue
        new_rows.append({"date": d, "spy_close": round(close, 2),
                         "spy_change_pct": round(chg, 2)})

    if new_rows:
        bench = pd.concat([bench, pd.DataFrame(new_rows)], ignore_index=True)
        bench.sort_values("date").to_csv(BENCH_PATH, index=False)
        log.info("Benchmark updated for %d date(s).", len(new_rows))


def load_benchmark() -> pd.DataFrame:
    if BENCH_PATH.exists():
        return pd.read_csv(BENCH_PATH, dtype={"date": str})
    return pd.DataFrame(columns=["date", "spy_close", "spy_change_pct"])


def backup_csvs() -> None:
    """Keep a rolling monthly backup of the data files so history can't be lost."""
    backup_dir = Path(__file__).parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    stamp = date.today().strftime("%Y-%m")
    for src in (CSV_PATH, BENCH_PATH):
        if src.exists():
            shutil.copy2(src, backup_dir / f"{src.stem}_{stamp}.csv")


def history_stats() -> dict:
    """Aggregate performance stats across all completed rows."""
    hist = _load()
    done = hist.dropna(subset=["day_change_pct"])
    if done.empty:
        return {}
    changes = done["day_change_pct"].astype(float)
    return {
        "days_tracked": done["date"].nunique(),
        "total_picks": len(done),
        "win_rate": (changes > 0).mean() * 100,
        "avg_change": changes.mean(),
        "best": f"{done.loc[changes.idxmax(), 'ticker']} {changes.max():+.2f}%",
        "worst": f"{done.loc[changes.idxmin(), 'ticker']} {changes.min():+.2f}%",
    }
