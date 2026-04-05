#!/usr/bin/env python3
"""
migrate.py — Flyway-style migration runner for running-ball-db.

Applies versioned SQL files in migrations/ (V*.sql) and optionally
seed files in seeds/ (S*.sql) in lexicographic order.

Each applied migration is checksummed and recorded in schema_migrations.
Re-running is idempotent: already-applied migrations are skipped.

Usage:
    python scripts/migrate.py                     # apply pending migrations
    python scripts/migrate.py --seeds             # also run seed files
    python scripts/migrate.py --dry-run           # print SQL only
"""

import hashlib
import logging
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "migrations"
SEEDS_DIR = REPO_ROOT / "seeds"

BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version      VARCHAR(50)  PRIMARY KEY,
    filename     VARCHAR(255) NOT NULL,
    checksum     CHAR(64)     NOT NULL,
    applied_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
"""


def checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()


def get_applied(conn) -> set:
    rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
    return {r[0] for r in rows}


def apply_file(conn, path: Path, dry_run: bool):
    sql = path.read_text(encoding="utf-8")
    cs = checksum(sql)
    version = path.stem          # e.g. "V001__baseline_schema"
    if dry_run:
        log.info("[DRY-RUN] Would apply: %s", path.name)
        print(f"\n-- {'='*60}")
        print(f"-- {path.name}")
        print(f"-- {'='*60}")
        print(sql)
        return
    conn.execute(text(sql))
    conn.execute(
        text("INSERT INTO schema_migrations (version, filename, checksum) "
             "VALUES (:v, :f, :c) ON CONFLICT (version) DO NOTHING"),
        {"v": version, "f": path.name, "c": cs},
    )
    log.info("Applied: %s", path.name)


@click.command()
@click.option("--db-url", envvar="DB_URL", required=True,
              help="SQLAlchemy DB URL (postgresql://user:pw@host/db)")
@click.option("--seeds", "run_seeds", is_flag=True, default=False,
              help="Also apply seed files from seeds/")
@click.option("--dry-run", is_flag=True, default=False,
              help="Print SQL without executing")
def main(db_url, run_seeds, dry_run):
    engine = create_engine(db_url, echo=False)

    with engine.begin() as conn:
        if not dry_run:
            conn.execute(text(BOOTSTRAP_SQL))
        applied = get_applied(conn) if not dry_run else set()

        # Migration files: V*.sql sorted by version prefix
        migration_files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
        for f in migration_files:
            if f.stem not in applied:
                apply_file(conn, f, dry_run)
            else:
                log.debug("Skipped (already applied): %s", f.name)

        # Optional seed files: S*.sql sorted
        if run_seeds:
            seed_files = sorted(SEEDS_DIR.glob("S*.sql"))
            for f in seed_files:
                if f.stem not in applied:
                    apply_file(conn, f, dry_run)
                else:
                    log.debug("Skipped (already applied): %s", f.name)

    log.info("Migration complete.")


if __name__ == "__main__":
    main()
