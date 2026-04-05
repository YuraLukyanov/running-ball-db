#!/usr/bin/env python3
"""
ingest.py — Bulk ingestion of match data files into Amazon RDS (PostgreSQL).

Supported input formats:  .csv  |  .xls  |  .xlsx

Each file must follow the structure from the "RB fixtures" export:
  Section 1 — Match metadata  (Country, Competition, Game Start Time,
                                Competitor 1, Competitor 2)
  Section 2 — Statistics      (Type column + value columns per team)
  Section 3 — Events          (Time, Minute, EventCode, Event)

The script:
  1. Parses every file in the input path
  2. Resolves or creates lookup rows (country, competition, teams)
  3. Upserts match metadata
  4. Bulk-inserts statistics via executemany (ON CONFLICT DO UPDATE)
  5. Bulk-inserts events via executemany (append-only)
  6. Reports per-file results and a summary

Usage:
    # Single file
    python scripts/ingest.py --file data/raw/match_2273387.xls

    # All files in a directory
    python scripts/ingest.py --dir data/raw/

    # Dry run (parse + validate only, no DB writes)
    python scripts/ingest.py --dir data/raw/ --dry-run

    # Override batch size
    python scripts/ingest.py --dir data/raw/ --batch-size 1000
"""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ingest")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MatchMeta:
    external_match_id: str
    country_name: str
    competition_name: str
    kickoff_raw: str          # e.g. "04.01.2026 - 14:00"
    home_team: str
    away_team: str
    kickoff_time: Optional[datetime] = None

    def parse_kickoff(self):
        """Convert '04.01.2026 - 14:00' → timezone-aware datetime (UTC)."""
        try:
            dt = datetime.strptime(self.kickoff_raw.strip(), "%d.%m.%Y - %H:%M")
            self.kickoff_time = dt.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError(
                f"Cannot parse kickoff time '{self.kickoff_raw}': {exc}"
            ) from exc


@dataclass
class StatRow:
    team_name: str
    stat_code: str
    stat_value: float
    period: str = "full"


@dataclass
class EventRow:
    clock_time_raw: str       # e.g. "14:09:35"
    match_minute: str         # e.g. "07:39"
    event_code: str           # e.g. "2053"
    event_detail: str
    team_name: Optional[str] = None
    zone: Optional[str] = None


@dataclass
class ParsedFile:
    source_path: Path
    meta: Optional[MatchMeta] = None
    stats: list[StatRow] = field(default_factory=list)
    events: list[EventRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Stat label → stat_code mapping  (from statistic_types seed)
# ---------------------------------------------------------------------------
STAT_LABEL_TO_CODE: dict[str, str] = {
    "score":                 "score",
    "corners (cr)":          "corners",
    "yellow cards (yc)":     "yellow_cards",
    "yellow/red cards (yc/rc)": "yellow_red_cards",
    "red cards (rc)":        "red_cards",
    "penalties (pen)":       "penalties",
    "free kicks (fk)":       "free_kicks",
    "dangerous free kicks":  "dangerous_free_kicks",
    "fouls":                 "fouls",
    "offsides":              "offsides",
    "shots (on target)":     "shots_on_target",
    "shots (off target)":    "shots_off_target",
    "shots (woodwork)":      "shots_woodwork",
    "shots (blocked)":       "shots_blocked",
    "goal kicks (gk)":       "goal_kicks",
    "throw ins (ti)":        "throw_ins",
    "attacks (at)":          "attacks",
    "dangerous attacks":     "dangerous_attacks",
    "breakaways":            "breakaways",
    "substitutions (sub)":   "substitutions",
}


# ---------------------------------------------------------------------------
# File reader
# ---------------------------------------------------------------------------

def read_raw_file(path: Path) -> pd.DataFrame:
    """Return a raw DataFrame (all strings, no headers) for any supported format."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    elif suffix in (".xls", ".xlsx"):
        engine_map = {".xls": "xlrd", ".xlsx": "openpyxl"}
        return pd.read_excel(
            path,
            header=None,
            dtype=str,
            keep_default_na=False,
            engine=engine_map[suffix],
        )
    else:
        raise ValueError(f"Unsupported file extension: {suffix}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> ParsedFile:
    result = ParsedFile(source_path=path)
    try:
        df = read_raw_file(path)
    except Exception as exc:
        result.errors.append(f"Cannot read file: {exc}")
        return result

    rows = df.values.tolist()
    # Flatten and strip every cell
    rows = [[str(c).strip() for c in row] for row in rows]

    # Detect section boundaries by scanning for section headers
    meta_start = stats_start = events_start = None
    for i, row in enumerate(rows):
        first = row[0] if row else ""
        if first == "Country":
            meta_start = i
        elif first == "Statistics":
            stats_start = i
        elif first == "Events":
            events_start = i

    # ── Match metadata ──
    result.meta = _parse_meta(rows, meta_start, path)
    if result.meta is None:
        result.errors.append("Could not locate match metadata section.")
        return result

    # ── Statistics ──
    if stats_start is not None:
        end = events_start if events_start else len(rows)
        stats, errs = _parse_stats(rows, stats_start, end, result.meta)
        result.stats.extend(stats)
        result.errors.extend(errs)

    # ── Events ──
    if events_start is not None:
        evts, errs = _parse_events(rows, events_start, len(rows))
        result.events.extend(evts)
        result.errors.extend(errs)

    return result


def _parse_meta(rows: list, start: int | None, path: Path) -> Optional[MatchMeta]:
    """Extract match metadata from header rows."""
    if start is None:
        return None

    kv: dict[str, str] = {}
    for row in rows[start:]:
        key = row[0] if row else ""
        val = row[1] if len(row) > 1 else ""
        if key in ("Country", "Competition", "Game Start Time",
                   "Competitor 1", "Competitor 2"):
            kv[key] = val

    # external_match_id: try to find a numeric-looking cell near the top
    ext_id = path.stem  # fallback to filename
    for row in rows[:10]:
        for cell in row:
            if cell.isdigit() and len(cell) >= 5:
                ext_id = cell
                break

    meta = MatchMeta(
        external_match_id=ext_id,
        country_name=kv.get("Country", "Unknown"),
        competition_name=kv.get("Competition", "Unknown"),
        kickoff_raw=kv.get("Game Start Time", ""),
        home_team=kv.get("Competitor 1", "Unknown"),
        away_team=kv.get("Competitor 2", "Unknown"),
    )
    try:
        meta.parse_kickoff()
    except ValueError as exc:
        log.warning("%s", exc)
    return meta


def _parse_stats(
    rows: list, start: int, end: int, meta: MatchMeta
) -> tuple[list[StatRow], list[str]]:
    """
    Parse the Statistics section. Layout expected:
      Row 0: "Statistics" header
      Row 1: "Type" | <home_team> | <away_team>
      Row 2+: <stat_label> | <home_value> | <away_value>
    """
    stats: list[StatRow] = []
    errors: list[str] = []
    section = rows[start:end]

    # Find the header row ("Type" in first col)
    header_idx = None
    for i, row in enumerate(section):
        if row and row[0].lower() == "type":
            header_idx = i
            break
    if header_idx is None:
        errors.append("Statistics: cannot find 'Type' header row.")
        return stats, errors

    home_col = 1
    away_col = 2

    for row in section[header_idx + 1:]:
        label = row[0].strip() if row else ""
        if not label or label.lower() == "type":
            continue
        stat_code = STAT_LABEL_TO_CODE.get(label.lower())
        if stat_code is None:
            # Unknown stat — add to catalog dynamically with raw label as code
            stat_code = re.sub(r"\W+", "_", label.lower()).strip("_")
            log.debug("Unknown stat label '%s' → code '%s'", label, stat_code)

        def safe_float(val: str) -> Optional[float]:
            try:
                return float(val.replace(",", "."))
            except (ValueError, AttributeError):
                return None

        home_val = safe_float(row[home_col]) if len(row) > home_col else None
        away_val = safe_float(row[away_col]) if len(row) > away_col else None

        if home_val is not None:
            stats.append(StatRow(meta.home_team, stat_code, home_val))
        if away_val is not None:
            stats.append(StatRow(meta.away_team, stat_code, away_val))

    return stats, errors


def _parse_events(
    rows: list, start: int, end: int
) -> tuple[list[EventRow], list[str]]:
    """
    Parse the Events section. Layout expected:
      Row 0: "Events" header
      Row 1: "Time" | "Minute" | "EventCode" | "Event"
      Row 2+: data rows
    """
    events: list[EventRow] = []
    errors: list[str] = []
    section = rows[start:end]

    # Find header row
    header_idx = None
    for i, row in enumerate(section):
        if row and row[0].lower() == "time":
            header_idx = i
            break
    if header_idx is None:
        errors.append("Events: cannot find 'Time' header row.")
        return events, errors

    # Column positions (default from schema)
    TIME_COL, MIN_COL, CODE_COL, EVENT_COL = 0, 1, 2, 3

    for row in section[header_idx + 1:]:
        # Skip empty / nearly empty rows
        non_empty = [c for c in row if c]
        if len(non_empty) < 2:
            continue

        clock = row[TIME_COL] if len(row) > TIME_COL else ""
        minute = row[MIN_COL] if len(row) > MIN_COL else ""
        code = row[CODE_COL] if len(row) > CODE_COL else ""
        detail = row[EVENT_COL] if len(row) > EVENT_COL else ""

        # Clean up codes that have trailing non-numeric chars (e.g. '532C', '1039A')
        code_clean = re.sub(r"[^0-9]", "", code) or code

        # Extract team name from detail if present
        team_name = _extract_team(detail)

        # Extract zone if present (e.g. "Zone A2 - Attacking half")
        zone_match = re.search(r"Zone\s+\w+\s*[-–]\s*[A-Za-z ]+", detail)
        zone = zone_match.group(0).strip() if zone_match else None

        events.append(EventRow(
            clock_time_raw=clock,
            match_minute=minute,
            event_code=code_clean,
            event_detail=detail,
            team_name=team_name,
            zone=zone,
        ))

    return events, errors


def _extract_team(detail: str) -> Optional[str]:
    """
    Heuristic: event detail often ends with a team name prefixed by spaces.
    Examples:
      'Goal   FC Nantes'         → 'FC Nantes'
      'FK   Olympique de Marseille (Zone...)' → 'Olympique de Marseille'
    """
    # Pattern: 3+ spaces followed by team name
    m = re.match(r".*\s{2,}([A-Z][A-Za-z .']+?)(?:\s*[,([]|$)", detail)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) > 2:
            return candidate
    return None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_or_create_country(conn: Connection, name: str) -> int:
    row = conn.execute(
        text("SELECT country_id FROM countries WHERE country_name = :n"), {"n": name}
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        text("INSERT INTO countries (country_name) VALUES (:n) "
             "RETURNING country_id"), {"n": name}
    ).fetchone()
    return row[0]


def get_or_create_competition(
    conn: Connection, name: str, country_id: int, season: str = None
) -> int:
    row = conn.execute(
        text("SELECT competition_id FROM competitions "
             "WHERE competition_name = :n AND country_id = :c "
             "AND (season = :s OR (season IS NULL AND :s IS NULL))"),
        {"n": name, "c": country_id, "s": season},
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        text("INSERT INTO competitions (competition_name, country_id, season) "
             "VALUES (:n, :c, :s) RETURNING competition_id"),
        {"n": name, "c": country_id, "s": season},
    ).fetchone()
    return row[0]


def get_or_create_team(conn: Connection, name: str, country_id: int) -> int:
    row = conn.execute(
        text("SELECT team_id FROM teams WHERE team_name = :n AND country_id = :c"),
        {"n": name, "c": country_id},
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        text("INSERT INTO teams (team_name, country_id) VALUES (:n, :c) "
             "RETURNING team_id"),
        {"n": name, "c": country_id},
    ).fetchone()
    return row[0]


def upsert_match(conn: Connection, meta: MatchMeta,
                 competition_id: int, home_id: int, away_id: int) -> int:
    row = conn.execute(
        text("SELECT match_id FROM matches WHERE external_match_id = :eid"),
        {"eid": meta.external_match_id},
    ).fetchone()
    if row:
        return row[0]
    kickoff = meta.kickoff_time or datetime.now(tz=timezone.utc)
    row = conn.execute(
        text("""
            INSERT INTO matches
                (external_match_id, competition_id, match_date, kickoff_time,
                 home_team_id, away_team_id, status)
            VALUES (:eid, :cid, :md, :kt, :ht, :at, 'finished')
            RETURNING match_id
        """),
        {
            "eid": meta.external_match_id,
            "cid": competition_id,
            "md": kickoff.date(),
            "kt": kickoff,
            "ht": home_id,
            "at": away_id,
        },
    ).fetchone()
    return row[0]


def get_stat_type_map(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT stat_code, stat_type_id FROM statistic_types")
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def ensure_stat_type(conn: Connection, stat_code: str,
                     stat_map: dict[str, int]) -> int:
    if stat_code in stat_map:
        return stat_map[stat_code]
    row = conn.execute(
        text("""
            INSERT INTO statistic_types (stat_code, stat_label, data_type)
            VALUES (:c, :l, 'integer')
            ON CONFLICT (stat_code) DO NOTHING
            RETURNING stat_type_id
        """),
        {"c": stat_code, "l": stat_code.replace("_", " ").title()},
    ).fetchone()
    if row:
        stat_map[stat_code] = row[0]
        return row[0]
    # Race condition — fetch again
    row = conn.execute(
        text("SELECT stat_type_id FROM statistic_types WHERE stat_code = :c"),
        {"c": stat_code},
    ).fetchone()
    stat_map[stat_code] = row[0]
    return row[0]


def get_event_type_map(conn: Connection) -> dict[str, int]:
    rows = conn.execute(
        text("SELECT event_code, event_type_id FROM event_types")
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def ensure_event_type(conn: Connection, event_code: str,
                      event_map: dict[str, int]) -> int:
    if event_code in event_map:
        return event_map[event_code]
    row = conn.execute(
        text("""
            INSERT INTO event_types (event_code, event_label)
            VALUES (:c, :l)
            ON CONFLICT (event_code) DO NOTHING
            RETURNING event_type_id
        """),
        {"c": event_code, "l": f"Event {event_code}"},
    ).fetchone()
    if row:
        event_map[event_code] = row[0]
        return row[0]
    row = conn.execute(
        text("SELECT event_type_id FROM event_types WHERE event_code = :c"),
        {"c": event_code},
    ).fetchone()
    event_map[event_code] = row[0]
    return row[0]


def get_team_id(conn: Connection, name: str,
                team_cache: dict[str, int]) -> Optional[int]:
    if not name:
        return None
    if name in team_cache:
        return team_cache[name]
    row = conn.execute(
        text("SELECT team_id FROM teams WHERE team_name = :n"), {"n": name}
    ).fetchone()
    if row:
        team_cache[name] = row[0]
        return row[0]
    # Fuzzy fallback: ILIKE
    row = conn.execute(
        text("SELECT team_id FROM teams WHERE team_name ILIKE :n"),
        {"n": f"%{name[:10]}%"},
    ).fetchone()
    if row:
        team_cache[name] = row[0]
        return row[0]
    return None


# ---------------------------------------------------------------------------
# Ingestion core
# ---------------------------------------------------------------------------

def ingest_parsed(
    conn: Connection,
    parsed: ParsedFile,
    batch_size: int,
    dry_run: bool,
) -> dict:
    """Persist one ParsedFile to the database. Returns a result summary dict."""
    result = {
        "file": str(parsed.source_path.name),
        "stats_inserted": 0,
        "events_inserted": 0,
        "errors": list(parsed.errors),
        "skipped": False,
    }

    if not parsed.meta:
        result["errors"].append("No metadata parsed — skipping.")
        result["skipped"] = True
        return result

    meta = parsed.meta
    log.info("Ingesting: %s  (%s vs %s)", parsed.source_path.name,
             meta.home_team, meta.away_team)

    if dry_run:
        log.info("[DRY-RUN] %d stats, %d events parsed — not written.",
                 len(parsed.stats), len(parsed.events))
        result["stats_inserted"] = len(parsed.stats)
        result["events_inserted"] = len(parsed.events)
        return result

    # ── Resolve / create lookup rows ──
    country_id = get_or_create_country(conn, meta.country_name)
    competition_id = get_or_create_competition(
        conn, meta.competition_name, country_id
    )
    home_id = get_or_create_team(conn, meta.home_team, country_id)
    away_id = get_or_create_team(conn, meta.away_team, country_id)
    match_id = upsert_match(conn, meta, competition_id, home_id, away_id)

    team_id_map = {meta.home_team: home_id, meta.away_team: away_id}
    stat_map = get_stat_type_map(conn)
    event_map = get_event_type_map(conn)

    # ── Bulk insert statistics ──
    stat_rows = []
    for s in parsed.stats:
        tid = team_id_map.get(s.team_name)
        if not tid:
            continue
        stid = ensure_stat_type(conn, s.stat_code, stat_map)
        stat_rows.append({
            "mid": match_id,
            "tid": tid,
            "stid": stid,
            "period": s.period,
            "val": s.stat_value,
        })

    for batch_start in range(0, len(stat_rows), batch_size):
        batch = stat_rows[batch_start: batch_start + batch_size]
        conn.execute(
            text("""
                INSERT INTO match_statistics
                    (match_id, team_id, stat_type_id, period, stat_value)
                VALUES (:mid, :tid, :stid, :period, :val)
                ON CONFLICT (match_id, team_id, stat_type_id, period)
                DO UPDATE SET stat_value = EXCLUDED.stat_value
            """),
            batch,
        )
        result["stats_inserted"] += len(batch)

    # ── Bulk insert events ──
    event_rows = []
    for e in parsed.events:
        if not e.event_code:
            continue
        etid = ensure_event_type(conn, e.event_code, event_map)
        team_id = get_team_id(conn, e.team_name or "", team_id_map) if e.team_name else None

        # Parse wall-clock time (combine with match date for full timestamp)
        clock_ts = None
        if e.clock_time_raw and re.match(r"^\d{2}:\d{2}:\d{2}", e.clock_time_raw):
            try:
                t = datetime.strptime(e.clock_time_raw[:8], "%H:%M:%S").time()
                clock_ts = datetime.combine(meta.kickoff_time.date(), t,
                                            tzinfo=timezone.utc)
            except ValueError:
                pass

        event_rows.append({
            "mid": match_id,
            "etid": etid,
            "tid": team_id,
            "ct": clock_ts,
            "mm": e.match_minute or None,
            "det": e.event_detail[:1000] if e.event_detail else None,
            "zone": e.zone,
        })

    for batch_start in range(0, len(event_rows), batch_size):
        batch = event_rows[batch_start: batch_start + batch_size]
        conn.execute(
            text("""
                INSERT INTO match_events
                    (match_id, event_type_id, team_id, clock_time,
                     match_minute, event_detail, zone)
                VALUES (:mid, :etid, :tid, :ct, :mm, :det, :zone)
            """),
            batch,
        )
        result["events_inserted"] += len(batch)

    log.info("  ✓ %d stats  |  %d events inserted  (match_id=%s)",
             result["stats_inserted"], result["events_inserted"], match_id)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx"}


def collect_files(file_path: Optional[Path], dir_path: Optional[Path]) -> list[Path]:
    files = []
    if file_path:
        files.append(file_path)
    if dir_path:
        for p in sorted(dir_path.iterdir()):
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
    return files


@click.command()
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path),
              help="Single input file (.csv / .xls / .xlsx)")
@click.option("--dir", "dir_path", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Directory containing input files")
@click.option("--db-url", envvar="DB_URL", required=False,
              help="PostgreSQL connection string (falls back to DB_URL env var)")
@click.option("--batch-size", default=int(os.getenv("DB_BATCH_SIZE", 500)),
              show_default=True, help="Rows per bulk insert batch")
@click.option("--dry-run", is_flag=True, default=False,
              help="Parse files and report without writing to DB")
def main(file_path, dir_path, db_url, batch_size, dry_run):
    """Ingest match data files (.csv / .xls / .xlsx) into PostgreSQL."""

    if not file_path and not dir_path:
        raise click.UsageError("Provide --file or --dir.")

    if not dry_run and not db_url:
        raise click.UsageError(
            "DB_URL is required unless --dry-run is set. "
            "Set it in .env or pass --db-url."
        )

    files = collect_files(file_path, dir_path)
    if not files:
        log.warning("No supported files found.")
        sys.exit(0)

    log.info("Found %d file(s) to process.", len(files))

    # Parse all files first (no DB needed)
    parsed_files = [parse_file(f) for f in files]

    # Report parse warnings
    for pf in parsed_files:
        for err in pf.errors:
            log.warning("[%s] %s", pf.source_path.name, err)

    if dry_run:
        for pf in parsed_files:
            if pf.meta:
                log.info("[DRY-RUN] %s: %s vs %s | %d stats | %d events",
                         pf.source_path.name,
                         pf.meta.home_team, pf.meta.away_team,
                         len(pf.stats), len(pf.events))
        log.info("Dry run complete. No data written.")
        sys.exit(0)

    # Connect and ingest
    engine = create_engine(
        db_url,
        pool_size=int(os.getenv("DB_POOL_SIZE", 5)),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
        echo=False,
    )

    summary = []
    for pf in parsed_files:
        try:
            with engine.begin() as conn:
                r = ingest_parsed(conn, pf, batch_size, dry_run)
                summary.append(r)
        except Exception as exc:
            log.error("[%s] Fatal error: %s", pf.source_path.name, exc, exc_info=True)
            summary.append({
                "file": pf.source_path.name,
                "stats_inserted": 0,
                "events_inserted": 0,
                "errors": [str(exc)],
                "skipped": True,
            })

    # ── Summary report ──
    print("\n" + "=" * 60)
    print("  INGESTION SUMMARY")
    print("=" * 60)
    total_stats = total_events = 0
    for r in summary:
        status = "SKIP" if r["skipped"] else "OK"
        print(f"  [{status}] {r['file']}")
        print(f"        stats={r['stats_inserted']}  events={r['events_inserted']}")
        if r["errors"]:
            for e in r["errors"]:
                print(f"        ⚠  {e}")
        total_stats += r["stats_inserted"]
        total_events += r["events_inserted"]
    print("-" * 60)
    print(f"  Total files : {len(summary)}")
    print(f"  Total stats : {total_stats}")
    print(f"  Total events: {total_events}")
    print("=" * 60)


if __name__ == "__main__":
    main()
