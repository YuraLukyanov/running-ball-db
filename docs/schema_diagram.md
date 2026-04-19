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
  home_corners / away_corners
  home_yellow_cards / away_yellow_cards
  home_yellow_red_cards / away_yellow_red_cards
  home_red_cards / away_red_cards
  home_penalties / away_penalties
  home_free_kicks / away_free_kicks
  home_dangerous_free_kicks / away_dangerous_free_kicks
  home_fouls / away_fouls
  home_offsides / away_offsides
  home_shots_on_target / away_shots_on_target
  home_shots_off_target / away_shots_off_target
  home_shots_woodwork / away_shots_woodwork
  home_shots_blocked / away_shots_blocked
  home_goal_kicks / away_goal_kicks
  home_throw_ins / away_throw_ins
  home_attacks / away_attacks
  home_dangerous_attacks / away_dangerous_attacks
  home_breakaways / away_breakaways
  home_substitutions / away_substitutions
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

## Match Statistics

All 20 statistics are stored directly on the `matches` table as paired
`home_<stat>` / `away_<stat>` columns (SMALLINT, nullable until the match
produces data). This avoids the overhead of the EAV pattern and makes queries
straightforward with no joins or pivots required.
