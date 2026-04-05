# Schema Diagram

```
countries ──────────────────────────────────────────────────────────────────┐
  country_id (PK)                                                            │
  country_name                                                               │
  iso_code                                                                   │
      │                                                                      │
      ▼                                                                      │
competitions                                               teams ────────────┘
  competition_id (PK)                                        team_id (PK)
  competition_name                                           team_name
  country_id (FK → countries)                               short_name
  season                                                     country_id (FK → countries)
      │
      ▼
matches ◄──────────────────── home_team_id (FK → teams)
  match_id (PK)                away_team_id (FK → teams)
  external_match_id
  competition_id (FK)
  match_date
  kickoff_time
  status
  home_score / away_score
      │
      ├──────────────────────► match_statistics
      │                          match_stat_id (PK)
      │                          match_id (FK → matches)
      │                          team_id (FK → teams)
      │                          stat_type_id (FK → statistic_types)
      │                          period
      │                          stat_value
      │                                │
      │                                ▼
      │                        statistic_types
      │                          stat_type_id (PK)
      │                          stat_code (UNIQUE)
      │                          stat_label
      │                          stat_category
      │
      ├──────────────────────► match_events
      │                          event_id (PK)
      │                          match_id (FK → matches)
      │                          event_type_id (FK → event_types)
      │                          team_id (FK → teams, nullable)
      │                          clock_time
      │                          match_minute
      │                          period
      │                          event_detail
      │                          zone
      │                                │
      │                                ▼
      │                        event_types
      │                          event_type_id (PK)
      │                          event_code (UNIQUE)
      │                          event_label
      │                          event_category
      │                          is_significant
      │
      └──────────────────────► match_periods
                                 match_period_id (PK)
                                 match_id (FK → matches)
                                 period
                                 started_at / ended_at
                                 stoppage_minutes
```

## EAV Pattern (Statistics)

Rather than a wide table with 20+ fixed stat columns, statistics are stored as
key-value pairs:

```
match_id=1, team_id=2, stat_type_id=3 ("corners"), period="full", stat_value=5
match_id=1, team_id=2, stat_type_id=9 ("fouls"),   period="full", stat_value=12
```

New stat types are added via `INSERT INTO statistic_types` — no DDL changes needed.
