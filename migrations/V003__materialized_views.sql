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
    MAX(CASE WHEN st.stat_code = 'corners'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_corners,
    MAX(CASE WHEN st.stat_code = 'corners'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_corners,
    MAX(CASE WHEN st.stat_code = 'shots_on_target'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_shots_on,
    MAX(CASE WHEN st.stat_code = 'shots_on_target'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_shots_on,
    MAX(CASE WHEN st.stat_code = 'fouls'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_fouls,
    MAX(CASE WHEN st.stat_code = 'fouls'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_fouls,
    MAX(CASE WHEN st.stat_code = 'yellow_cards'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_yellow_cards,
    MAX(CASE WHEN st.stat_code = 'yellow_cards'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_yellow_cards,
    MAX(CASE WHEN st.stat_code = 'attacks'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_attacks,
    MAX(CASE WHEN st.stat_code = 'attacks'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_attacks,
    MAX(CASE WHEN st.stat_code = 'dangerous_attacks'
             AND ms.team_id = m.home_team_id THEN ms.stat_value END) AS home_dangerous_attacks,
    MAX(CASE WHEN st.stat_code = 'dangerous_attacks'
             AND ms.team_id = m.away_team_id THEN ms.stat_value END) AS away_dangerous_attacks
FROM matches m
JOIN competitions c    ON c.competition_id  = m.competition_id
JOIN countries co      ON co.country_id     = c.country_id
JOIN teams ht          ON ht.team_id        = m.home_team_id
JOIN teams at2         ON at2.team_id       = m.away_team_id
LEFT JOIN match_statistics ms ON ms.match_id = m.match_id AND ms.period = 'full'
LEFT JOIN statistic_types st  ON st.stat_type_id = ms.stat_type_id
GROUP BY
    m.match_id, m.external_match_id, m.match_date, m.kickoff_time, m.status,
    c.competition_name, co.country_name, ht.team_name, at2.team_name,
    m.home_score, m.away_score
WITH NO DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_match_summary_id ON mv_match_summary (match_id);
CREATE INDEX IF NOT EXISTS idx_mv_match_summary_date      ON mv_match_summary (match_date);
CREATE INDEX IF NOT EXISTS idx_mv_match_summary_status    ON mv_match_summary (status);
