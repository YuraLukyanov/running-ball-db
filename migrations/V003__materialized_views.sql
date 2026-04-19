-- =============================================================================
-- Migration:  V003__materialized_views.sql
-- Description: Materialized view for match summary cards
-- Refresh:     REFRESH MATERIALIZED VIEW CONCURRENTLY mv_match_summary;
--              (run via scripts/refresh_views.py after each match finishes)
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_match_summary AS
SELECT
    m.match_id,
    m.external_match_id,
    m.match_date,
    m.kickoff_time,
    m.status,
    c.competition_name,
    co.country_name,
    ht.team_name  AS home_team,
    at2.team_name AS away_team,
    m.home_score,
    m.away_score,
    m.home_corners,
    m.away_corners,
    m.home_shots_on_target,
    m.away_shots_on_target,
    m.home_fouls,
    m.away_fouls,
    m.home_yellow_cards,
    m.away_yellow_cards,
    m.home_attacks,
    m.away_attacks,
    m.home_dangerous_attacks,
    m.away_dangerous_attacks
FROM matches m
JOIN competitions c ON c.competition_id = m.competition_id
JOIN countries co   ON co.country_id    = c.country_id
JOIN teams ht       ON ht.team_id       = m.home_team_id
JOIN teams at2      ON at2.team_id      = m.away_team_id
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_match_summary_id ON mv_match_summary (match_id);
CREATE INDEX IF NOT EXISTS idx_mv_match_summary_date      ON mv_match_summary (match_date);
CREATE INDEX IF NOT EXISTS idx_mv_match_summary_status    ON mv_match_summary (status);
