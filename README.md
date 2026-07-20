# Daily Stock Picks Agent

Claude stock agent that sends me daily stock picks.

Every weekday morning (before US market open), this agent:

1. Pulls the current S&P 500 ticker list and a year of daily price history.
2. Filters for liquid names in uptrends: price above the 20- and 50-day
   averages, 50-day above 200-day, RSI below 75, average dollar volume
   over $20M.
3. Ranks survivors by blended 1/3/6-month momentum plus proximity to the
   52-week high, and takes the top 5.
4. Emails the picks as a formatted table with price, momentum, RSI, distance
   from the 52-week high, and the 20-day low as a support reference.
5. Records the picks in `picks_history.csv` for performance tracking.

A second task runs every weekday at **5:00 PM** (after the 4:00 PM market
close): it fills in each pick's closing price and day change (%) in
`picks_history.csv`, records the S&P 500 (SPY) benchmark for the day,
regenerates `dashboard.html`, backs up the data files to `backups/`, then
emails a confirmation with the day's results and the running record
(win rate, average day change, best/worst pick).

## Dashboard

Open `dashboard.html` in any browser (double-click it). It is fully
self-contained, works offline, supports light/dark mode, and is rebuilt from
the complete CSV history after every run — so it always shows everything and
never loses data. It includes:

- KPI tiles: cumulative return vs the S&P 500, win rate, average day change
  per pick, days beating the S&P 500, days/picks tracked
- Cumulative return chart (equal-weight pick portfolio vs SPY, compounded)
- Daily result chart (each day's average pick return vs SPY the same day)
- Performance by pick rank (does the screen's #1 beat its #5?)
- Full pick history table with search, day summaries, and beat/trail chips
- Date-range filters (all time / 90 / 30 / 7 days) that scope every view

## One-time setup (required before emails will send)

The agent sends mail through your own Gmail account using a Google
**App Password** (a 16-character code that only works for this one purpose
and can be revoked anytime — it is not your real password).

1. Go to <https://myaccount.google.com/apppasswords> (you must have
   2-Step Verification enabled on the Google account).
2. Create an app password named e.g. `stock agent` and copy the 16-character code.
3. In this folder, copy `.env.example` to `.env` and paste the code:

   ```
   GMAIL_ADDRESS=your.agent.account@gmail.com
   GMAIL_APP_PASSWORD=abcdabcdabcdabcd
   RECIPIENT=where.to.send@gmail.com
   ```

4. Test it: open a terminal in this folder and run `python stock_agent.py`.
   You should receive the email within a minute.

## Files

| File | Purpose |
| --- | --- |
| `stock_agent.py` | Morning entry point — runs the screen, sends the email, records picks |
| `eod_update.py` | Evening entry point — saves closing prices, sends confirmation |
| `screener.py` | Universe, filters, and momentum ranking |
| `emailer.py` | HTML/text rendering and Gmail SMTP send |
| `tracker.py` | picks_history.csv read/write, SPY benchmark, backups, stats |
| `dashboard.py` | Regenerates dashboard.html from the full CSV history |
| `dashboard.html` | The performance dashboard — open in a browser |
| `picks_history.csv` | One row per pick per day: pick price, close, day change % |
| `benchmark_history.csv` | S&P 500 (SPY) close and day change per tracked date |
| `backups/` | Rolling monthly copies of both CSVs |
| `run_agent.bat` / `run_eod.bat` | What Task Scheduler runs; output goes to `task_run.log` |
| `.env` | Your email credentials (never share or commit this) |
| `agent.log` / `task_run.log` | Run history for troubleshooting |

## Useful commands

```powershell
python stock_agent.py --dry-run    # run the screen, write picks_preview.html, no email
python stock_agent.py --top 10     # email 10 picks instead of 5
python eod_update.py --dry-run     # fill in closes in the CSV, no email
schtasks /run /tn "Daily Stock Picks"      # trigger the morning job right now
schtasks /run /tn "Daily Stock Picks EOD"  # trigger the evening update right now
schtasks /change /tn "Daily Stock Picks" /st 07:00       # change the morning time
schtasks /change /tn "Daily Stock Picks EOD" /st 18:00   # change the evening time
schtasks /delete /tn "Daily Stock Picks" /f              # remove a schedule
```

Note: the PC must be awake at 8:30 AM for the task to fire; if it was off,
Task Scheduler skips that day.

## Adjusting the strategy

All screening logic lives in `screener.py`:

- Filters (price, dollar volume, trend, RSI cap) are in `_score_ticker`.
- The ranking weights are in the `score` formula — currently 35% 3-month
  return, 25% 1-month, 20% 6-month, 20% closeness to the 52-week high.

## Disclaimer

This is a rules-based screen for informational purposes only — not investment
advice. Momentum screens can and do pick losers; position sizing and risk
management are on you.
