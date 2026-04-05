-- =============================================================================
-- Seed: S001__stat_types.sql
-- Description: Reference rows for statistic_types (safe to re-run — uses
--              INSERT ... ON CONFLICT DO NOTHING)
-- =============================================================================

INSERT INTO statistic_types (stat_code, stat_label, stat_category, data_type) VALUES
    ('score',               'Score',                    'result',      'integer'),
    ('corners',             'Corners (CR)',              'set_pieces',  'integer'),
    ('yellow_cards',        'Yellow cards (YC)',         'discipline',  'integer'),
    ('yellow_red_cards',    'Yellow/red cards (YC/RC)', 'discipline',  'integer'),
    ('red_cards',           'Red cards (RC)',            'discipline',  'integer'),
    ('penalties',           'Penalties (PEN)',           'set_pieces',  'integer'),
    ('free_kicks',          'Free kicks (FK)',           'set_pieces',  'integer'),
    ('dangerous_free_kicks','Dangerous free kicks',      'set_pieces',  'integer'),
    ('fouls',               'Fouls',                    'discipline',  'integer'),
    ('offsides',            'Offsides',                 'general',     'integer'),
    ('shots_on_target',     'Shots (on target)',         'shots',       'integer'),
    ('shots_off_target',    'Shots (off target)',        'shots',       'integer'),
    ('shots_woodwork',      'Shots (woodwork)',          'shots',       'integer'),
    ('shots_blocked',       'Shots (blocked)',           'shots',       'integer'),
    ('goal_kicks',          'Goal kicks (GK)',           'set_pieces',  'integer'),
    ('throw_ins',           'Throw ins (TI)',            'set_pieces',  'integer'),
    ('attacks',             'Attacks (AT)',              'possession',  'integer'),
    ('dangerous_attacks',   'Dangerous attacks',         'possession',  'integer'),
    ('breakaways',          'Breakaways',               'possession',  'integer'),
    ('substitutions',       'Substitutions (SUB)',       'general',     'integer')
ON CONFLICT (stat_code) DO NOTHING;
