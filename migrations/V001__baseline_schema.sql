-- =============================================================================
-- Migration:  V001__baseline_schema.sql
-- Description: Baseline schema — all core tables
-- Author:      running-ball-db
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. COUNTRIES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS countries (
    country_id   SMALLSERIAL   PRIMARY KEY,
    country_name VARCHAR(100)  NOT NULL UNIQUE,
    iso_code     CHAR(2)       UNIQUE,
    created_at   TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. COMPETITIONS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competitions (
    competition_id   SERIAL        PRIMARY KEY,
    competition_name VARCHAR(200)  NOT NULL,
    country_id       SMALLINT      NOT NULL REFERENCES countries(country_id),
    season           VARCHAR(20),
    tier             SMALLINT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (competition_name, country_id, season)
);

-- ---------------------------------------------------------------------------
-- 3. TEAMS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    team_id    SERIAL        PRIMARY KEY,
    team_name  VARCHAR(200)  NOT NULL,
    short_name VARCHAR(50),
    country_id SMALLINT      REFERENCES countries(country_id),
    created_at TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (team_name, country_id)
);

-- ---------------------------------------------------------------------------
-- 4. MATCHES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    match_id          BIGSERIAL     PRIMARY KEY,
    external_match_id VARCHAR(50)   UNIQUE,
    competition_id    INT           NOT NULL REFERENCES competitions(competition_id),
    match_date        DATE          NOT NULL,
    kickoff_time      TIMESTAMPTZ   NOT NULL,
    home_team_id      INT           NOT NULL REFERENCES teams(team_id),
    away_team_id      INT           NOT NULL REFERENCES teams(team_id),
    status            VARCHAR(20)   NOT NULL DEFAULT 'scheduled'
                          CHECK (status IN ('scheduled','live','half_time',
                                            'finished','cancelled','postponed')),
    home_score                SMALLINT,
    away_score                SMALLINT,
    home_corners              SMALLINT,
    away_corners              SMALLINT,
    home_yellow_cards         SMALLINT,
    away_yellow_cards         SMALLINT,
    home_yellow_red_cards     SMALLINT,
    away_yellow_red_cards     SMALLINT,
    home_red_cards            SMALLINT,
    away_red_cards            SMALLINT,
    home_penalties            SMALLINT,
    away_penalties            SMALLINT,
    home_free_kicks           SMALLINT,
    away_free_kicks           SMALLINT,
    home_dangerous_free_kicks SMALLINT,
    away_dangerous_free_kicks SMALLINT,
    home_fouls                SMALLINT,
    away_fouls                SMALLINT,
    home_offsides             SMALLINT,
    away_offsides             SMALLINT,
    home_shots_on_target      SMALLINT,
    away_shots_on_target      SMALLINT,
    home_shots_off_target     SMALLINT,
    away_shots_off_target     SMALLINT,
    home_shots_woodwork       SMALLINT,
    away_shots_woodwork       SMALLINT,
    home_shots_blocked        SMALLINT,
    away_shots_blocked        SMALLINT,
    home_goal_kicks           SMALLINT,
    away_goal_kicks           SMALLINT,
    home_throw_ins            SMALLINT,
    away_throw_ins            SMALLINT,
    home_attacks              SMALLINT,
    away_attacks              SMALLINT,
    home_dangerous_attacks    SMALLINT,
    away_dangerous_attacks    SMALLINT,
    home_breakaways           SMALLINT,
    away_breakaways           SMALLINT,
    home_substitutions        SMALLINT,
    away_substitutions        SMALLINT,
    attendance        INT,
    venue             VARCHAR(200),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT chk_different_teams CHECK (home_team_id <> away_team_id)
);

-- ---------------------------------------------------------------------------
-- 5. EVENT TYPES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS event_types (
    event_type_id    SERIAL        PRIMARY KEY,
    event_code       VARCHAR(20)   NOT NULL UNIQUE,
    event_label      VARCHAR(200)  NOT NULL,
    event_category   VARCHAR(50),
    is_significant   BOOLEAN       NOT NULL DEFAULT FALSE,
    description      TEXT,
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 6. MATCH EVENTS  (timeline)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_events (
    event_id       BIGSERIAL     PRIMARY KEY,
    match_id       BIGINT        NOT NULL REFERENCES matches(match_id),
    event_type_id  INT           NOT NULL REFERENCES event_types(event_type_id),
    team_id        INT           REFERENCES teams(team_id),
    clock_time     TIMESTAMPTZ,
    match_minute   VARCHAR(10),
    period         VARCHAR(10)   CHECK (period IN ('pre','1h','2h','et1','et2','pen','post')),
    event_detail   TEXT,
    zone           VARCHAR(100),
    sequence_no    INT,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 7. MATCH PERIODS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_periods (
    match_period_id  BIGSERIAL    PRIMARY KEY,
    match_id         BIGINT       NOT NULL REFERENCES matches(match_id),
    period           VARCHAR(10)  NOT NULL CHECK (period IN ('1h','2h','et1','et2','pen')),
    started_at       TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    stoppage_minutes SMALLINT     DEFAULT 0,
    UNIQUE (match_id, period)
);

-- ---------------------------------------------------------------------------
-- Trigger: auto-update matches.updated_at
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_matches_updated_at ON matches;
CREATE TRIGGER trg_matches_updated_at
    BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
