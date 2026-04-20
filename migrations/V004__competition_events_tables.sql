-- =============================================================================
-- Migration:  V004__competition_events_tables.sql
-- Description: Add events_table_name column to competitions.
--              Per-competition match_events_<slug> tables are created
--              dynamically by the running-ball-export-transformer pipeline
--              when a new competition is first encountered.
-- =============================================================================

ALTER TABLE competitions
    ADD COLUMN IF NOT EXISTS events_table_name VARCHAR(200);
