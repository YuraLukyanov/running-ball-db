"""
Unit tests for scripts/ingest.py parsers.
Run with: pytest tests/
"""

import sys
from pathlib import Path

import pytest

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from ingest import (
    MatchMeta,
    _extract_team,
    _parse_events,
    _parse_meta,
    _parse_stats,
)


# ---------------------------------------------------------------------------
# MatchMeta.parse_kickoff
# ---------------------------------------------------------------------------

def test_parse_kickoff_valid():
    m = MatchMeta("1", "France", "Ligue 1", "04.01.2026 - 14:00", "OM", "FCN")
    m.parse_kickoff()
    assert m.kickoff_time is not None
    assert m.kickoff_time.year == 2026
    assert m.kickoff_time.month == 1
    assert m.kickoff_time.day == 4
    assert m.kickoff_time.hour == 14


def test_parse_kickoff_invalid():
    m = MatchMeta("1", "France", "Ligue 1", "not-a-date", "OM", "FCN")
    with pytest.raises(ValueError):
        m.parse_kickoff()


# ---------------------------------------------------------------------------
# _extract_team
# ---------------------------------------------------------------------------

def test_extract_team_simple():
    assert _extract_team("Goal   FC Nantes") == "FC Nantes"


def test_extract_team_with_zone():
    result = _extract_team(
        "FK   Olympique de Marseille (Zone 5 - defensive FK), Zone A3"
    )
    assert result == "Olympique de Marseille"


def test_extract_team_none():
    assert _extract_team("Coin flipping") is None


# ---------------------------------------------------------------------------
# _parse_meta
# ---------------------------------------------------------------------------

def make_rows_meta():
    return [
        ["Country", "France", "", ""],
        ["Competition", "Ligue 1", "", ""],
        ["Game Start Time", "04.01.2026 - 14:00", "", ""],
        ["Competitor 1", "Olympique de Marseille", "", ""],
        ["Competitor 2", "FC Nantes", "", ""],
    ]


def test_parse_meta_happy_path(tmp_path):
    rows = make_rows_meta()
    meta = _parse_meta(rows, 0, tmp_path / "2273387.xls")
    assert meta.country_name == "France"
    assert meta.competition_name == "Ligue 1"
    assert meta.home_team == "Olympique de Marseille"
    assert meta.away_team == "FC Nantes"


def test_parse_meta_missing_section(tmp_path):
    meta = _parse_meta([], None, tmp_path / "test.xls")
    assert meta is None


# ---------------------------------------------------------------------------
# _parse_stats
# ---------------------------------------------------------------------------

def make_rows_stats():
    meta_rows = make_rows_meta()
    stats_rows = [
        ["Statistics", "", "", ""],
        ["Type", "Olympique de Marseille", "FC Nantes", ""],
        ["Corners (CR)", "5", "3", ""],
        ["Fouls", "12", "9", ""],
        ["Yellow cards (YC)", "2", "1", ""],
    ]
    return meta_rows + stats_rows, len(meta_rows)


def test_parse_stats_basic():
    rows, stats_start = make_rows_stats()
    from ingest import MatchMeta
    meta = MatchMeta("1", "France", "Ligue 1", "04.01.2026 - 14:00",
                     "Olympique de Marseille", "FC Nantes")
    stats, errs = _parse_stats(rows, stats_start, len(rows), meta)
    assert not errs
    codes = {s.stat_code for s in stats}
    assert "corners" in codes
    assert "fouls" in codes
    home_corners = next(s for s in stats
                        if s.stat_code == "corners" and s.team_name == "Olympique de Marseille")
    assert home_corners.stat_value == 5.0


# ---------------------------------------------------------------------------
# _parse_events
# ---------------------------------------------------------------------------

def make_rows_events():
    return [
        ["Events", "", "", ""],
        ["Time", "Minute", "EventCode", "Event"],
        ["14:02:08", "00:00", "101", "Start 1st half, kickoff:   Olympique de Marseille"],
        ["14:09:48", "07:39", "2053", "[0 : 1]   Goal   FC Nantes"],
        ["14:11:08", "08:59", "533", "VAR Start"],
        ["14:15:06", "12:58", "2054", "[0 : 0]   Cancel Goal   FC Nantes"],
    ]


def test_parse_events_basic():
    rows = make_rows_events()
    events, errs = _parse_events(rows, 0, len(rows))
    assert not errs
    assert len(events) == 4
    goal = next(e for e in events if e.event_code == "2053")
    assert "FC Nantes" in (goal.team_name or "")
    assert goal.match_minute == "07:39"


def test_parse_events_code_cleanup():
    rows = [
        ["Events", "", "", ""],
        ["Time", "Minute", "EventCode", "Event"],
        ["14:00:41", "00:00", "532C", "Formation changed"],
    ]
    events, _ = _parse_events(rows, 0, len(rows))
    assert events[0].event_code == "532"
