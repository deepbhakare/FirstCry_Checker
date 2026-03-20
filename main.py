"""
main.py — Entry point for FirstCry Tracker
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bootstraps config, database, notifier and kicks off a single
scrape cycle. Railway cron calls this every 5 minutes.

Exit codes:
  0 — run completed successfully
  1 — fatal error (also sends Telegram error alert)
"""

import logging
import sys

from config import AppConfig
from db import Database
from notifier import Notifier
from scraper import run


# ─── LOGGING SETUP ────────────────────────────────────────────────────────────

def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Silence noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


# ─── BOOTSTRAP ────────────────────────────────────────────────────────────────

def main() -> None:
    _configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Initialising FirstCry Tracker...")

    config   = AppConfig()
    db       = Database(config.database)
    notifier = Notifier(config.telegram)

    try:
        run(config, db, notifier)
    except Exception as exc:
        logger.critical(f"Fatal unhandled error: {exc}", exc_info=True)
        notifier.alert_error("main()", exc)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
