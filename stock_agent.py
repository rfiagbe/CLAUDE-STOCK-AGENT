"""Daily stock picks agent.

Runs the momentum screen and emails the top picks.

Usage:
    python stock_agent.py             # screen + send email (needs .env configured)
    python stock_agent.py --dry-run   # screen only; writes picks_preview.html
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dashboard import generate_dashboard
from emailer import render_html, render_text, send_email
from screener import run_screen
from tracker import record_picks

HERE = Path(__file__).parent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(HERE / "agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("stock_agent")


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily stock picks agent")
    parser.add_argument("--dry-run", action="store_true",
                        help="run the screen but don't send email")
    parser.add_argument("--top", type=int, default=5, help="number of picks")
    args = parser.parse_args()

    load_dotenv(HERE / ".env")

    picks = run_screen(top_n=args.top)
    if picks.empty:
        log.error("Screen returned no candidates; not sending email.")
        return 1

    print(render_text(picks))

    if args.dry_run:
        preview = HERE / "picks_preview.html"
        preview.write_text(render_html(picks), encoding="utf-8")
        log.info("Dry run: preview written to %s (picks not recorded to CSV)", preview)
        return 0

    record_picks(picks)
    generate_dashboard()  # show today's pending picks right away

    sender = os.getenv("GMAIL_ADDRESS", "")
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    recipient = os.getenv("RECIPIENT", sender)
    if not sender or not app_password:
        log.error("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set in .env — "
                  "see README.md for setup. Run with --dry-run to test without email.")
        return 1

    send_email(picks, sender, app_password, recipient)
    return 0


if __name__ == "__main__":
    sys.exit(main())
