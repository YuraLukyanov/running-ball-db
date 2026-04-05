#!/usr/bin/env python3
"""
refresh_views.py — Refresh materialized views concurrently.

Run this after a batch of matches finishes, or on a cron schedule:
    python scripts/refresh_views.py
"""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("refresh_views")

VIEWS = ["mv_match_summary"]


def main():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise RuntimeError("DB_URL environment variable is not set.")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execution_options(isolation_level="AUTOCOMMIT")
        for view in VIEWS:
            log.info("Refreshing %s ...", view)
            conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}"))
            log.info("Done: %s", view)


if __name__ == "__main__":
    main()
