"""Renders the daily picks as HTML and sends them via Gmail SMTP."""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

log = logging.getLogger(__name__)

DISCLAIMER = (
    "This email is generated automatically by a rules-based momentum screen for "
    "informational purposes only. It is not investment advice or a recommendation "
    "to buy or sell any security. Do your own research before trading."
)


def _pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def render_html(picks: pd.DataFrame) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    rows = []
    for ticker, r in picks.iterrows():
        rows.append(f"""
        <tr>
          <td style="padding:10px 12px;font-weight:700;">{ticker}<br>
              <span style="font-weight:400;color:#666;font-size:12px;">{r['name']}</span></td>
          <td style="padding:10px 12px;text-align:right;">${r['price']:,.2f}</td>
          <td style="padding:10px 12px;text-align:right;color:{'#0a7f3f' if r['ret_1m'] >= 0 else '#c0392b'};">{_pct(r['ret_1m'])}</td>
          <td style="padding:10px 12px;text-align:right;color:{'#0a7f3f' if r['ret_3m'] >= 0 else '#c0392b'};">{_pct(r['ret_3m'])}</td>
          <td style="padding:10px 12px;text-align:right;">{r['rsi']:.0f}</td>
          <td style="padding:10px 12px;text-align:right;">{_pct(r['pct_from_high'])}</td>
          <td style="padding:10px 12px;text-align:right;">${r['low_20d']:,.2f}</td>
        </tr>""")

    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:720px;margin:0 auto;color:#222;">
      <h2 style="margin-bottom:2px;">📈 Daily Stock Picks</h2>
      <p style="color:#666;margin-top:0;">{today} &middot; Momentum screen of the S&amp;P 500</p>
      <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <thead>
          <tr style="background:#1a1a2e;color:#fff;text-align:right;">
            <th style="padding:10px 12px;text-align:left;">Ticker</th>
            <th style="padding:10px 12px;">Price</th>
            <th style="padding:10px 12px;">1M</th>
            <th style="padding:10px 12px;">3M</th>
            <th style="padding:10px 12px;">RSI</th>
            <th style="padding:10px 12px;">vs 52w high</th>
            <th style="padding:10px 12px;">20d low</th>
          </tr>
        </thead>
        <tbody style="background:#fafafa;">{''.join(rows)}</tbody>
      </table>
      <p style="font-size:12px;color:#888;margin-top:16px;">
        Screen: price above 20/50-day averages, 50-day above 200-day, RSI &lt; 75,
        avg dollar volume &gt; $20M. Ranked by blended 1/3/6-month momentum and
        proximity to the 52-week high. "20d low" is the lowest close of the last
        20 sessions, shown as a recent support reference.
      </p>
      <p style="font-size:11px;color:#aaa;border-top:1px solid #ddd;padding-top:10px;">{DISCLAIMER}</p>
    </div>"""


def render_text(picks: pd.DataFrame) -> str:
    lines = [f"Daily Stock Picks - {date.today().isoformat()}", ""]
    for ticker, r in picks.iterrows():
        lines.append(
            f"{ticker:6} ${r['price']:>9,.2f}  1M {_pct(r['ret_1m']):>7}  "
            f"3M {_pct(r['ret_3m']):>7}  RSI {r['rsi']:>3.0f}"
        )
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def _send(subject: str, text: str, html: str,
          sender: str, app_password: str, recipient: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as server:
        server.login(sender, app_password)
        server.sendmail(sender, [recipient], msg.as_string())
    log.info("Email sent to %s", recipient)


def send_email(picks: pd.DataFrame, sender: str, app_password: str, recipient: str) -> None:
    _send(f"📈 Daily Stock Picks — {date.today().strftime('%b %d, %Y')}",
          render_text(picks), render_html(picks), sender, app_password, recipient)


def render_eod_html(updated: pd.DataFrame, stats: dict) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    rows = []
    for _, r in updated.iterrows():
        chg = float(r["day_change_pct"])
        color = "#0a7f3f" if chg >= 0 else "#c0392b"
        rows.append(f"""
        <tr>
          <td style="padding:8px 12px;font-weight:700;">{r['ticker']}</td>
          <td style="padding:8px 12px;text-align:right;">${float(r['pick_price']):,.2f}</td>
          <td style="padding:8px 12px;text-align:right;">${float(r['close_price']):,.2f}</td>
          <td style="padding:8px 12px;text-align:right;font-weight:700;color:{color};">{chg:+.2f}%</td>
        </tr>""")

    stats_html = ""
    if stats:
        stats_html = f"""
      <p style="font-size:13px;color:#444;background:#f2f4f8;padding:10px 14px;border-radius:6px;">
        <b>Running record:</b> {stats['days_tracked']} days &middot; {stats['total_picks']} picks tracked
        &middot; win rate {stats['win_rate']:.0f}% &middot; avg day change {stats['avg_change']:+.2f}%<br>
        Best: {stats['best']} &nbsp;&middot;&nbsp; Worst: {stats['worst']}
      </p>"""

    return f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:0 auto;color:#222;">
      <h2 style="margin-bottom:2px;">✅ Picks Tracker Updated</h2>
      <p style="color:#666;margin-top:0;">{today} &middot; Closing prices saved to picks_history.csv</p>
      <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <thead>
          <tr style="background:#1a1a2e;color:#fff;text-align:right;">
            <th style="padding:8px 12px;text-align:left;">Ticker</th>
            <th style="padding:8px 12px;">Pick price</th>
            <th style="padding:8px 12px;">Close</th>
            <th style="padding:8px 12px;">Day change</th>
          </tr>
        </thead>
        <tbody style="background:#fafafa;">{''.join(rows)}</tbody>
      </table>
      {stats_html}
      <p style="font-size:11px;color:#aaa;border-top:1px solid #ddd;padding-top:10px;">{DISCLAIMER}</p>
    </div>"""


def send_eod_email(updated: pd.DataFrame, stats: dict,
                   sender: str, app_password: str, recipient: str) -> None:
    lines = [f"Picks tracker updated - {date.today().isoformat()}", ""]
    for _, r in updated.iterrows():
        lines.append(f"{r['ticker']:6} pick ${float(r['pick_price']):>9,.2f}  "
                     f"close ${float(r['close_price']):>9,.2f}  "
                     f"{float(r['day_change_pct']):+.2f}%")
    _send(f"✅ Picks Tracker Updated — {date.today().strftime('%b %d, %Y')}",
          "\n".join(lines), render_eod_html(updated, stats),
          sender, app_password, recipient)
