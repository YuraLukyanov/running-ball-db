-- =============================================================================
-- Migration:  V002__indexes.sql
-- Description: All performance indexes
-- =============================================================================

-- Matches
CREATE INDEX IF NOT EXISTS idx_matches_date          ON matches (match_date);
CREATE INDEX IF NOT EXISTS idx_matches_competition   ON matches (competition_id, match_date);
CREATE INDEX IF NOT EXISTS idx_matches_home_team     ON matches (home_team_id, match_date);
CREATE INDEX IF NOT EXISTS idx_matches_away_team     ON matches (away_team_id, match_date);
CREATE INDEX IF NOT EXISTS idx_matches_external_id   ON matches (external_match_id);
CREATE INDEX IF NOT EXISTS idx_matches_status        ON matches (status)
    WHERE status IN ('live', 'scheduled');

-- Match statistics
CREATE INDEX IF NOT EXISTS idx_match_stats_match     ON match_statistics (match_id);
CREATE INDEX IF NOT EXISTS idx_match_stats_team_stat ON match_statistics (team_id, stat_type_id);
CREATE INDEX IF NOT EXISTS idx_match_stats_lookup    ON match_statistics (match_id, team_id, stat_type_id);

-- Match events — primary access pattern: timeline per match
CREATE INDEX IF NOT EXISTS idx_events_match_time     ON match_events (match_id, clock_time);
CREATE INDEX IF NOT EXISTS idx_events_match_minute   ON match_events (match_id, match_minute);
CREATE INDEX IF NOT EXISTS idx_events_type           ON match_events (event_type_id);
CREATE INDEX IF NOT EXISTS idx_events_team           ON match_events (team_id, match_id);

-- Partial index: significant events only (goals, cards, subs) for live dashboards
CREATE INDEX IF NOT EXISTS idx_events_significant    ON match_events (match_id, clock_time)
    WHERE event_type_id IN (
        SELECT event_type_id FROM event_types WHERE is_significant = TRUE
    );

-- Statistic types lookup
CREATE INDEX IF NOT EXISTS idx_stat_types_code       ON statistic_types (stat_code);
CREATE INDEX IF NOT EXISTS idx_event_types_code      ON event_types (event_code);
