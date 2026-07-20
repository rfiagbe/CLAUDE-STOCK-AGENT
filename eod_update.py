"""End-of-day job: fill in closing prices for tracked picks and email a confirmation.

Usage:
    python eod_update.py             # update CSV + send confirmation email
    python eod_update.py --dry-run   # update CSV only, no email
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from dashboard import generate_dashboard
from emailer import send_eod_email
from tracker import backup_csvs, history_stats, update_benchmark, update_closes

HERE = Path(__file__).parent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(HERE / "agent.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("eod_update")


def main() -> int:
    parser = argparse.ArgumentParser(description="EOD tracker update")
    parser.add_argument("--dry-run", action="store_true",
                        help="update the CSV but don't send email")
    args = parser.parse_args()

    load_dotenv(HERE / ".env")

    updated = update_closes()
    update_benchmark()
    generate_dashboard()
    backup_csvs()

    if updated.empty:
        log.info("Nothing was updated; dashboard refreshed, skipping confirmation email.")
        return 0

    for _, r in updated.iterrows():
        print(f"{r['ticker']:6} pick ${float(r['pick_price']):>9,.2f}  "
              f"close ${float(r['close_price']):>9,.2f}  "
              f"{float(r['day_change_pct']):+.2f}%")

    if args.dry_run:
        log.info("Dry run: skipping confirmation email.")
        return 0

    sender = os.getenv("GMAIL_ADDRESS", "")
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
    recipient = os.getenv("RECIPIENT", sender)
    if not sender or not app_password:
        log.error("Email credentials missing in .env; CSV was updated but no email sent.")
        return 1

    send_eod_email(updated, history_stats(), sender, app_password, recipient)
    return 0


if __name__ == "__main__":
    sys.exit(main())
