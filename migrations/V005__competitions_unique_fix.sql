-- =============================================================================
-- Migration:  V005__competitions_unique_fix.sql
-- Description: Replace the (competition_name, country_id, season) unique
--              constraint with two partial unique indexes so that NULL-season
--              rows are also deduplicated.
--
-- Root cause: PostgreSQL treats NULL != NULL in unique indexes, so the
-- original UNIQUE (competition_name, country_id, season) allowed any number
-- of rows with the same name/country and season = NULL, producing duplicates
-- that caused ON CONFLICT DO UPDATE cardinality violations in match inserts.
--
-- Fix:
--   1. Drop the old constraint.
--   2. Add a partial unique index for rows WHERE season IS NULL
--      (covers the common pipeline case — no season data in source files).
--   3. Add a partial unique index for rows WHERE season IS NOT NULL
--      (preserves correct behaviour for future seasonal data).
-- =============================================================================

-- Remove any duplicate NULL-season rows before adding the constraint,
-- keeping the row with the lowest competition_id.
DELETE FROM competitions
WHERE competition_id NOT IN (
    SELECT MIN(competition_id)
    FROM   competitions
    GROUP BY competition_name, country_id, season
);

-- Drop the old constraint (it was created as a named constraint by Postgres
-- from the inline UNIQUE clause; the auto-generated name follows the pattern
-- competitions_competition_name_country_id_season_key).
ALTER TABLE competitions
    DROP CONSTRAINT IF EXISTS competitions_competition_name_country_id_season_key;

-- Partial index: NULL season (pipeline default — source files carry no season)
CREATE UNIQUE INDEX IF NOT EXISTS uq_competitions_name_country_null_season
    ON competitions (competition_name, country_id)
    WHERE season IS NULL;

-- Partial index: non-NULL season (future seasonal competition tracking)
CREATE UNIQUE INDEX IF NOT EXISTS uq_competitions_name_country_season
    ON competitions (competition_name, country_id, season)
    WHERE season IS NOT NULL;
